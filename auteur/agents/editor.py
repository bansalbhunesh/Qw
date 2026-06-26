"""Editor / Critic — the Qwen-VL review loop plus final assembly.

The critic is the multimodal heart of Auteur: Qwen-VL *watches* a rendered clip (sampled
frames, passed as data URIs) and scores it against the shot's intent on three axes. The Budget
Governor then decides whether a failing clip is worth a reshoot. Approved clips are assembled
with crossfade transitions and optional dialogue overlay.
"""

from __future__ import annotations

from pathlib import Path

from .. import log, media
from ..budget import BudgetGovernor
from ..llm import QwenClient
from ..models import Shot

STAGE = "critic"
_log = log.get("editor")

_CRITIC_SYS = """\
You are a ruthless but fair film editor reviewing a single shot from a short drama. You score \
the rendered frames against the intended shot description.

Score 0-10 on each axis:
- prompt_adherence: does the rendered image match what was requested? (composition, action, setting)
- character_consistency: do characters look as described? (age, clothing, features)
- shot_quality: cinematic quality — lighting, focus, framing, mood.

Return ONLY valid JSON:
{"prompt_adherence": n, "character_consistency": n, "shot_quality": n, "overall": n, \
"fix": "if overall < 7, write ONE specific, concrete prompt modification to fix the weakest \
axis. If overall >= 7, empty string."}"""


class Editor:
    def __init__(self, client: QwenClient, governor: BudgetGovernor):
        self.client = client
        self.governor = governor

    def sample_frames(self, clip_path: str, n: int = 3) -> list[str]:
        """Extract frames and return as data URIs the Qwen-VL critic can consume."""
        frames = media.extract_frames(clip_path, n=n)
        return [media.frame_to_data_uri(f) for f in frames]

    def critique(self, shot: Shot, frame_uris: list[str]) -> dict:
        """Have Qwen-VL watch sampled frames and score the clip."""
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"INTENDED SHOT:\n{shot.description}\n\n"
                    f"VIDEO PROMPT USED:\n{shot.video_prompt}\n\n"
                    f"Score the {len(frame_uris)} frames below from the rendered clip."
                ),
            },
        ]
        for uri in frame_uris:
            content.append({"type": "image_url", "image_url": {"url": uri}})

        result = self.client.vision(
            STAGE,
            [{"role": "system", "content": _CRITIC_SYS}, {"role": "user", "content": content}],
        )

        if isinstance(result, dict):
            overall = float(result.get("overall", 5.0))
            fix = str(result.get("fix", ""))
            _log.info(
                "shot %d critic: overall=%.1f  adherence=%.1f  consistency=%.1f  quality=%.1f%s",
                shot.index,
                overall,
                float(result.get("prompt_adherence", 0)),
                float(result.get("character_consistency", 0)),
                float(result.get("shot_quality", 0)),
                f"  fix: {fix[:60]}" if fix else "",
            )
            return result

        _log.warning("critic returned non-dict for shot %d, defaulting", shot.index)
        return {"overall": 5.0, "fix": ""}

    @staticmethod
    def assemble(
        clip_paths: list[str],
        out_path: str | Path,
        *,
        audio_paths: list[str | None] | None = None,
        crossfade: bool = True,
    ) -> str:
        """Assemble approved clips into one vertical short.

        If audio_paths are provided, each clip gets its dialogue overlaid before assembly.
        Uses crossfade transitions between clips for cinematic quality.
        """
        final_clips: list[str] = []
        out_path = Path(out_path)

        if audio_paths:
            for i, (clip, audio) in enumerate(zip(clip_paths, audio_paths)):
                if audio and Path(audio).exists():
                    merged = str(out_path.parent / f"merged_{i}.mp4")
                    merged = media.overlay_audio(clip, audio, merged)
                    final_clips.append(merged)
                else:
                    final_clips.append(clip)
        else:
            final_clips = list(clip_paths)

        if crossfade and len(final_clips) >= 2:
            return media.concat_with_crossfade(final_clips, out_path)
        return media.concat_clips(final_clips, out_path)

    @staticmethod
    def add_score(video_path: str, music_path: str, out_path: str | Path) -> str:
        """Mix the music bed under the assembled cut. Returns the final video path."""
        return media.mix_music(video_path, music_path, out_path)
