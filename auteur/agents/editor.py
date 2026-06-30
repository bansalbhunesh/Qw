"""Editor / Critic — the Qwen-VL review loop plus final assembly.

The critic is the multimodal heart of Auteur: Qwen-VL *watches* a rendered clip (sampled
frames, passed as data URIs) and scores it against the shot's intent on four axes, including
cross-shot visual continuity. The Budget Governor then decides whether a failing clip is worth
a reshoot. Approved clips are assembled with crossfade transitions and optional dialogue overlay.
"""

from __future__ import annotations

from pathlib import Path

from .. import log, media
from ..budget import BudgetGovernor
from ..events import bus
from ..llm import QwenClient
from ..models import Shot

STAGE = "critic"
_log = log.get("editor")

_CRITIC_SYS = """\
You are a ruthless, adversarial, and uncompromising film critic grading an AI-generated video shot. \
Your job is NOT to be nice; your job is to aggressively penalize hallucinations, warping, and drift. \
You are scoring the rendered frames against the intended shot description.

Score 0-10 on each axis. A score of 7+ means flawless photorealism. Grade harshly.
- prompt_adherence: does the rendered image match what was requested? Penalize heavily for missing subjects.
- character_consistency: do characters look as described? Penalize heavily for morphing or AI-artifacts.
- shot_quality: cinematic quality — lighting, focus, framing, mood.
- visual_continuity: does this shot feel like it belongs in the same film as the previous shot? \
(same characters, same wardrobe, consistent color grade, coherent world). Score 8 if this is the first shot.

Return ONLY valid JSON:
{"prompt_adherence": n, "character_consistency": n, "shot_quality": n, "visual_continuity": n, \
"overall": n, \
"usable_duration": n.n, \
"fix": "if overall < 7, write ONE specific, concrete prompt modification to fix the weakest \
axis. If overall >= 7, empty string."}

For `usable_duration`: Current AI video models often degrade temporally (physics break, objects morph) near the end of the clip. Analyze the progression of frames. If degradation occurs, set `usable_duration` to the exact second (e.g., 3.2) right before the break. If the clip is flawless until the end, set it to 5.0."""


class Editor:
    """Qwen-VL critic loop and final video assembly.

    Scores rendered clips on four axes (prompt adherence, character consistency,
    shot quality, visual continuity), advises the Governor on reshoots, and
    assembles approved clips with crossfade transitions and dialogue overlay.
    """

    def __init__(self, client: QwenClient, governor: BudgetGovernor):
        self.client = client
        self.governor = governor

    def sample_frames(self, clip_path: str, n: int = 3) -> list[str]:
        """Extract frames and return as data URIs the Qwen-VL critic can consume."""
        frames = media.extract_frames(clip_path, n=n)
        return [media.frame_to_data_uri(f) for f in frames]

    def critique(
        self,
        shot: Shot,
        frame_uris: list[str],
        prev_frame_uris: list[str] | None = None,
    ) -> dict:
        """Have Qwen-VL watch sampled frames and score the clip.

        If prev_frame_uris is provided (frames from the previous shot), the critic also
        evaluates cross-shot visual continuity — same characters, wardrobe, color grade.
        """
        text_parts = [
            f"INTENDED SHOT:\n{shot.description}\n\n"
            f"VIDEO PROMPT USED:\n{shot.video_prompt}\n\n"
        ]
        if prev_frame_uris:
            text_parts.append(
                f"The first {len(prev_frame_uris)} image(s) are from the PREVIOUS shot "
                f"(for continuity reference). The remaining {len(frame_uris)} image(s) are "
                f"from the CURRENT shot being reviewed.\n\n"
            )
        text_parts.append(f"Score the {len(frame_uris)} frames from the rendered clip.")

        content: list[dict] = [{"type": "text", "text": "".join(text_parts)}]
        if prev_frame_uris:
            for uri in prev_frame_uris:
                content.append({"type": "image_url", "image_url": {"url": uri}})
        for uri in frame_uris:
            content.append({"type": "image_url", "image_url": {"url": uri}})

        result = self.client.vision(
            STAGE,
            [{"role": "system", "content": _CRITIC_SYS}, {"role": "user", "content": content}],
        )

        if isinstance(result, dict):
            overall = float(result.get("overall", 5.0))
            fix = str(result.get("fix", ""))
            continuity = float(result.get("visual_continuity", 0))
            _log.info(
                "shot %d critic: overall=%.1f  adherence=%.1f  consistency=%.1f  "
                "quality=%.1f  continuity=%.1f%s",
                shot.index,
                overall,
                float(result.get("prompt_adherence", 0)),
                float(result.get("character_consistency", 0)),
                float(result.get("shot_quality", 0)),
                continuity,
                f"  fix: {fix[:60]}" if fix else "",
            )
            bus.emit("critic_verdict", STAGE,
                     index=shot.index, overall=overall,
                     prompt_adherence=float(result.get("prompt_adherence", 0)),
                     character_consistency=float(result.get("character_consistency", 0)),
                     shot_quality=float(result.get("shot_quality", 0)),
                     visual_continuity=continuity,
                     fix=fix[:80])
            return result

        _log.warning("critic returned non-dict for shot %d, defaulting", shot.index)
        return {"overall": 5.0, "fix": ""}

    @staticmethod
    def plan_transitions(beats: list | None) -> list[str]:
        """Pick a transition style for each cut based on adjacent beat tones.

        Returns a list of N-1 transitions for N clips. The decision:
        - Same or similar tone → dissolve (continuity)
        - Contrasting tone → hard cut (punctuation)
        - Any tone → cathartic/climax → fade (dramatic emphasis)
        """
        if not beats or len(beats) < 2:
            return []
        climactic = {"cathartic", "climax", "triumphant"}
        transitions: list[str] = []
        for i in range(len(beats) - 1):
            t1 = getattr(beats[i], "tone", "") if hasattr(beats[i], "tone") else beats[i].get("tone", "")
            t2 = getattr(beats[i + 1], "tone", "") if hasattr(beats[i + 1], "tone") else beats[i + 1].get("tone", "")
            if t2.lower() in climactic:
                transitions.append("fade")
            elif t1 == t2:
                transitions.append("dissolve")
            else:
                transitions.append("cut")
        return transitions

    @staticmethod
    def assemble(
        shots: list[Shot],
        out_path: str | Path,
        *,
        audio_paths: list[str | None] | None = None,
        crossfade: bool = True,
        transitions: list[str] | None = None,
    ) -> str:
        """Assemble approved clips into one vertical short.

        Trims clips based on Qwen-VL's `usable_duration` to remove temporal degradation.
        If audio_paths are provided, each clip gets its dialogue overlaid before assembly.
        Uses crossfade transitions between clips for cinematic quality.
        """
        final_clips: list[str] = []
        out_path = Path(out_path)

        for i, shot in enumerate(shots):
            clip = shot.clip_path
            if not clip:
                continue
                
            # Trim the fat (temporal degradation) before assembly
            trimmed = str(out_path.parent / f"trimmed_{i}.mp4")
            if shot.usable_duration and shot.usable_duration > 0:
                clip = media.trim_video(clip, shot.usable_duration, trimmed)

            audio = audio_paths[i] if audio_paths and i < len(audio_paths) else None
            merged = str(out_path.parent / f"merged_{i}.mp4")
            merged = media.overlay_audio(clip, audio, merged)
            final_clips.append(merged)

        if crossfade and len(final_clips) >= 2:
            return media.concat_with_crossfade(final_clips, out_path)
        return media.concat_clips(final_clips, out_path)

    @staticmethod
    def add_score(video_path: str, music_path: str, out_path: str | Path) -> str:
        """Mix the music bed under the assembled cut. Returns the final video path."""
        return media.mix_music(video_path, music_path, out_path)
