"""Writer — premise to structured screenplay.

Narrative ability is a judged criterion. We force structure:
premise -> logline -> beat sheet (with per-beat importance) -> shot-level script with dialogue
and cinematic video prompts. Importance flows from beats to shots and later drives the retake
budget and the critic's reshoot allocation.
"""

from __future__ import annotations

from .. import log
from ..config import Tier
from ..llm import QwenClient
from ..models import Beat, Script, Shot

STAGE = "writer"
_log = log.get("writer")

_BEATSHEET_SYS = """\
You are a veteran short-drama screenwriter with 20 years of experience in micro-format \
storytelling. You write tight, emotionally precise vertical short dramas (9:16, ~60s total). \
You think in beats. Every beat serves a narrative purpose — no filler.

Principles:
- HOOK: the first 3 seconds must arrest attention. Start mid-action or with a visual surprise.
- ECONOMY: every shot must advance plot AND reveal character simultaneously.
- SUBTEXT: the best dialogue says one thing and means another.
- BUTTON: end on an emotional beat that recontextualizes what came before.

Return ONLY valid JSON. No markdown, no commentary."""

_BEATSHEET_USER = """\
Premise: {premise}

Write a {shots}-beat micro-drama. Return JSON:
{{
  "logline": "one compelling sentence that captures the central dramatic question",
  "beats": [
    {{
      "label": "Hook|Setup|Escalation|Turn|Crisis|Climax|Button",
      "summary": "what happens in this beat — be specific about action, emotion, and stakes",
      "importance": 0.0-1.0,
      "tone": "the emotional register: tense|melancholy|tender|urgent|bittersweet|hopeful"
    }}
  ]
}}
Rules:
- The Hook MUST earn attention in the first 3 seconds. Give it importance >= 0.9.
- The Button MUST land an emotional punch. Give it importance >= 0.8.
- Exactly {shots} beats. Importance reflects how much the entire piece depends on that beat \
succeeding visually.
- Each beat must be achievable in a single continuous shot (~5-10 seconds of video)."""

_SHOTS_SYS = """\
You are a cinematographer-screenwriter hybrid. You write shot descriptions that a text-to-video \
AI model can render faithfully. You think in camera language: shot size, movement, lighting, \
blocking, depth of field. Return ONLY valid JSON."""

_SHOTS_USER = """\
Logline: {logline}
Beats:
{beats}

Style: {style_hint}

For EACH beat, write one shot. Return JSON:
{{
  "shots": [
    {{
      "beat_index": 0,
      "description": "what we SEE on screen — camera angle, subject blocking, action, lighting",
      "dialogue": "the exact spoken line for this shot, or empty string if no dialogue",
      "video_prompt": "a self-contained, vivid text-to-video prompt. RULES: (1) describe \
every person by physical appearance — age, build, hair, clothing, skin tone — never use names. \
(2) specify camera: shot size (CU/MCU/MS/WS), movement (static/push-in/pan/tracking), lens \
(35mm/50mm/85mm). (3) specify lighting (practical/natural/neon/golden-hour). (4) specify mood \
and color palette. (5) include 'vertical 9:16 aspect ratio' in every prompt."
    }}
  ]
}}
One shot per beat, in order. Make video_prompts maximally concrete and renderable."""


class Writer:
    def __init__(self, client: QwenClient):
        self.client = client

    def write(self, premise: str, shots: int, style_hint: str = "") -> Script:
        _log.info("writing %d-beat script for: %s", shots, premise[:60])

        beat_data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _BEATSHEET_SYS},
                {"role": "user", "content": _BEATSHEET_USER.format(premise=premise, shots=shots)},
            ],
            temperature=0.9,
        )
        beats = self._parse_beats(beat_data)
        _log.info("beat sheet: %s", " -> ".join(b.label for b in beats))

        beats_rendered = "\n".join(
            f"{b.index}. [{b.label}] (importance={b.importance:.1f}) {b.summary}" for b in beats
        )
        shot_data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _SHOTS_SYS},
                {"role": "user", "content": _SHOTS_USER.format(
                    logline=beat_data.get("logline", ""),
                    beats=beats_rendered,
                    style_hint=style_hint or "cinematic, emotional, visually striking",
                )},
            ],
            temperature=0.7,
        )
        shot_list = self._parse_shots(shot_data, beats)

        script = Script(
            premise=premise,
            logline=beat_data.get("logline", ""),
            beats=beats,
            shots=shot_list,
        )
        _log.info("script complete: %d beats, %d shots, logline: %s",
                  len(beats), len(shot_list), script.logline[:60])
        return script

    @staticmethod
    def _parse_beats(data: dict) -> list[Beat]:
        beats = []
        for i, b in enumerate(data.get("beats", [])):
            importance = float(b.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
            beats.append(Beat(
                index=i,
                label=b.get("label", f"Beat {i}"),
                summary=b.get("summary", ""),
                importance=importance,
            ))
        return beats

    @staticmethod
    def _parse_shots(data: dict, beats: list[Beat]) -> list[Shot]:
        shots = []
        for i, s in enumerate(data.get("shots", [])):
            bi = int(s.get("beat_index", i))
            importance = beats[bi].importance if bi < len(beats) else 0.5
            shots.append(Shot(
                index=i,
                beat_index=bi,
                description=s.get("description", ""),
                dialogue=s.get("dialogue", ""),
                video_prompt=s.get("video_prompt", ""),
                importance=importance,
            ))
        return shots
