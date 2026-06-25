"""Editor / Critic — the Qwen-VL review loop plus final assembly.

The critic is the multimodal heart of Auteur: Qwen-VL *watches* a rendered clip (sampled
frames) and scores it against the shot's intent on three axes. The Budget Governor then decides
whether a failing clip is worth a reshoot. Approved clips are assembled with ffmpeg into a
vertical short.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..budget import BudgetGovernor
from ..llm import QwenClient
from ..models import Shot

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

    def critique(self, shot: Shot, frame_urls: list[str]) -> dict:
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
        for url in frame_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        result = self.client.vision(
            STAGE,
            [
                {"role": "system", "content": _CRITIC_SYS},
                {"role": "user", "content": content},
            ],
        )
        return result if isinstance(result, dict) else {"overall": 5.0, "fix": ""}

    @staticmethod
    def assemble(clip_paths: list[str], audio_paths: list[str | None], out_path: str | Path) -> str:
        """Concatenate approved clips (with per-shot audio) into one vertical short via ffmpeg.

        Hardened during the build; the concat-demuxer flow is sketched here.
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        concat_file = out_path.with_suffix(".txt")
        concat_file.write_text("".join(f"file '{p}'\n" for p in clip_paths))
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c", "copy", str(out_path)],
            check=True,
        )
        return str(out_path)
