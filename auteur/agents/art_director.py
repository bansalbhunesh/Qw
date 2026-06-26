"""Art Director — builds the Character & Style Bible, the visual consistency engine.

Cross-shot character consistency is the hardest visual problem in AI short drama. Instead of
re-describing characters in every Wan prompt (expensive + drifty), we generate one canonical
Style Bible and *inject* it into every shot prompt. This is the asset-caching win the Budget
Governor relies on — the Bible is generated ONCE and reused across every shot.
"""

from __future__ import annotations

from .. import log
from ..config import Tier
from ..llm import QwenClient
from ..models import Character, Script, StyleBible

STAGE = "art_director"
_log = log.get("art_dir")

_SYS = """\
You are a world-class film art director and visual designer. Given a script, define a single \
consistent visual identity for the entire piece. Your descriptions must be concrete enough \
that a text-to-video AI model renders the same person, the same look, and the same world in \
every shot. Return ONLY valid JSON."""

_USER = """\
Logline: {logline}
Number of shots: {n_shots}
Shots:
{shots}

Return JSON:
{{
  "look": "one comprehensive line defining the visual world: color grade, lens/focal length, \
lighting style, film stock feel, aspect ratio. Example: 'muted teal-amber grade, 35mm \
anamorphic, shallow depth of field, soft practical lighting, warm amber highlights, cool shadow \
tones, vertical 9:16'",
  "palette": "three dominant colors as descriptive names, e.g. 'slate blue, warm amber, deep charcoal'",
  "characters": [
    {{
      "name": "character name",
      "description": "COMPLETE physical appearance: exact age range, build, height impression, \
hair (color, length, style), eye color, skin tone, facial features, clothing (specific items, \
colors, textures), any distinguishing marks or accessories. Must be detailed enough to render \
consistently across multiple shots without any additional context.",
      "voice": "warm|gravelly|youthful|neutral|deep|soft|commanding|gentle|husky|crisp"
    }}
  ]
}}
CRITICAL: character descriptions must be self-contained — a text-to-video model should produce \
the same person from the description alone, with zero external context."""


class ArtDirector:
    def __init__(self, client: QwenClient):
        self.client = client

    def build_bible(self, script: Script) -> StyleBible:
        shots_rendered = "\n".join(
            f"{s.index}. [{script.beats[s.beat_index].label if s.beat_index < len(script.beats) else '?'}] "
            f"{s.description}"
            for s in script.shots
        )
        _log.info("building Style Bible for %d shots", len(script.shots))

        data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _SYS},
                {"role": "user", "content": _USER.format(
                    logline=script.logline,
                    shots=shots_rendered,
                    n_shots=len(script.shots),
                )},
            ],
            temperature=0.6,
        )
        characters = [
            Character(
                name=c.get("name", ""),
                description=c.get("description", ""),
                voice=c.get("voice", "neutral"),
            )
            for c in data.get("characters", [])
        ]
        bible = StyleBible(
            look=data.get("look", ""),
            palette=data.get("palette", ""),
            characters=characters,
        )
        _log.info(
            "Style Bible: %d characters, look: %s",
            len(characters), bible.look[:80],
        )
        return bible

    @staticmethod
    def apply(bible: StyleBible, video_prompt: str) -> str:
        """Inject the cached look + character descriptions into a per-shot prompt.

        The injected text is appended (not prepended) so the shot-specific action stays
        prominent in the prompt — video models weight the beginning more heavily.
        """
        parts = [video_prompt.rstrip(". ") + "."]

        if bible.characters:
            char_block = " | ".join(
                f"{c.name}: {c.description}" for c in bible.characters
            )
            parts.append(f"Characters in this scene — {char_block}.")

        style_desc = bible.look
        if bible.palette:
            style_desc = f"{style_desc}. Color palette: {bible.palette}" if style_desc else f"Color palette: {bible.palette}"
        if style_desc:
            parts.append(f"Visual style — {style_desc}.")

        return " ".join(parts)
