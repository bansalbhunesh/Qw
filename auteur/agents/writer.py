"""Writer — premise to structured screenplay.

Narrative ability is a judged criterion, so we don't one-shot a script. We force structure:
premise -> logline -> a beat sheet (with per-beat importance) -> shot-level script with
dialogue. Importance flows from beats to shots and later drives the retake budget.
"""

from __future__ import annotations

from ..config import Tier
from ..llm import QwenClient
from ..models import Beat, Script, Shot

STAGE = "writer"

_BEATSHEET_SYS = (
    "You are a veteran short-drama screenwriter. You write tight, emotionally precise "
    "vertical short dramas (9:16, ~60s). You think in beats. Return ONLY JSON."
)

_BEATSHEET_USER = """Premise: {premise}

Write a {shots}-beat micro-drama. Return JSON:
{{
  "logline": "one sentence",
  "beats": [
    {{"label": "Hook|Setup|Turn|Crisis|Button", "summary": "...", "importance": 0.0-1.0}}
  ]
}}
Rules:
- The opening Hook must earn attention in the first 3 seconds; give it the highest importance.
- Exactly {shots} beats. Importance reflects how much the whole piece depends on that beat."""

_SHOTS_USER = """Logline: {logline}
Beats:
{beats}

For EACH beat, write one shot. Return JSON:
{{
  "shots": [
    {{
      "beat_index": 0,
      "description": "what we SEE on screen (camera, blocking, action)",
      "dialogue": "spoken line, or empty string",
      "video_prompt": "a vivid, self-contained text-to-video prompt (no character names; "
                      "describe appearance so a video model renders it consistently)"
    }}
  ]
}}
Keep video_prompts concrete and renderable. One shot per beat, in order."""


class Writer:
    def __init__(self, client: QwenClient):
        self.client = client

    def write(self, premise: str, shots: int) -> Script:
        beat_data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _BEATSHEET_SYS},
                {"role": "user", "content": _BEATSHEET_USER.format(premise=premise, shots=shots)},
            ],
        )
        beats = [
            Beat(
                index=i,
                label=b.get("label", f"Beat {i}"),
                summary=b.get("summary", ""),
                importance=float(b.get("importance", 0.5)),
            )
            for i, b in enumerate(beat_data.get("beats", []))
        ]

        beats_rendered = "\n".join(f"{b.index}. [{b.label}] {b.summary}" for b in beats)
        shot_data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _BEATSHEET_SYS},
                {
                    "role": "user",
                    "content": _SHOTS_USER.format(
                        logline=beat_data.get("logline", ""), beats=beats_rendered
                    ),
                },
            ],
        )

        shot_list: list[Shot] = []
        for i, s in enumerate(shot_data.get("shots", [])):
            bi = int(s.get("beat_index", i))
            importance = beats[bi].importance if bi < len(beats) else 0.5
            shot_list.append(
                Shot(
                    index=i,
                    beat_index=bi,
                    description=s.get("description", ""),
                    dialogue=s.get("dialogue", ""),
                    video_prompt=s.get("video_prompt", ""),
                    importance=importance,
                )
            )

        return Script(
            premise=premise,
            logline=beat_data.get("logline", ""),
            beats=beats,
            shots=shot_list,
        )
