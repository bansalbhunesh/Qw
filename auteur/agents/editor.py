"""Editor / Critic — the Qwen-VL review loop plus final assembly.

The critic is the multimodal heart of Auteur: Qwen-VL *watches* a rendered clip (sampled
frames, passed as data URIs) and scores it against the shot's intent on three axes. The Budget
Governor then decides whether a failing clip is worth a reshoot. Approved clips are assembled
with ffmpeg into a vertical short.
"""

from __future__ import annotations

from pathlib import Path

from ..budget import BudgetGovernor
from ..llm import QwenClient
from ..models import Shot
from .. import media

STAGE = "critic"

_CRITIC_SYS = (
    "You are a ruthless but fair film editor reviewing a single shot. Score 0-10 on each axis. "
    "Return ONLY JSON: "
    '{"prompt_adherence": n, "character_consistency": n, "shot_quality": n, '
    '"overall": n, "fix": "if overall<7, one concrete prompt change; else empty"}'
)


class Editor:
    def __init__(self, client: QwenClient, governor: BudgetGovernor):
        self.client = client
        self.governor = governor

    def sample_frames(self, clip_path: str, n: int = 3) -> list[str]:
        """Extract frames and return them as data URIs the Qwen-VL critic can consume."""
        frames = media.extract_frames(clip_path, n=n)
        return [media.frame_to_data_uri(f) for f in frames]

    def critique(self, shot: Shot, frame_uris: list[str]) -> dict:
        """Have Qwen-VL watch sampled frames and score the clip."""
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"Intended shot: {shot.description}\n"
                    f"Prompt used: {shot.video_prompt}\n"
                    "Score these frames from the rendered clip."
                ),
            }
        ]
        for uri in frame_uris:
            content.append({"type": "image_url", "image_url": {"url": uri}})

        result = self.client.vision(
            STAGE,
            [{"role": "system", "content": _CRITIC_SYS}, {"role": "user", "content": content}],
        )
        return result if isinstance(result, dict) else {"overall": 5.0, "fix": ""}

    @staticmethod
    def assemble(clip_paths: list[str], out_path: str | Path) -> str:
        """Concatenate approved clips into one vertical short via ffmpeg."""
        return media.concat_clips(clip_paths, out_path)
