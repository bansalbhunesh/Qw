"""Art Director — builds the Character & Style Bible once, so every shot stays consistent.

Cross-shot character consistency is the hardest visual problem in AI short drama. Instead of
re-describing characters in every Wan prompt (expensive + drifty), we generate one canonical
Style Bible and *inject* it into every shot prompt. This is the asset-caching win the Budget
Governor relies on.
"""

from __future__ import annotations

from ..config import Tier
from ..llm import QwenClient
from ..models import Character, Script, StyleBible

STAGE = "art_director"

_SYS = (
    "You are a film art director. Given a script, define a single consistent visual identity "
    "for the whole piece. Return ONLY JSON."
)

_USER = """Logline: {logline}
Shots:
{shots}

Return JSON:
{{
  "look": "one line: grade, lens, lighting, mood — applied to every shot",
  "characters": [
    {{"name": "...", "description": "fixed physical appearance, wardrobe, age", "voice": "warm|gravelly|youthful|neutral"}}
  ]
}}
Describe appearance concretely enough that a text-to-video model renders the same person every time."""


class ArtDirector:
    def __init__(self, client: QwenClient):
        self.client = client

    def build_bible(self, script: Script) -> StyleBible:
        shots_rendered = "\n".join(f"{s.index}. {s.description}" for s in script.shots)
        data = self.client.chat_json(
            STAGE,
            Tier.CREATIVE,
            [
                {"role": "system", "content": _SYS},
                {"role": "user", "content": _USER.format(logline=script.logline, shots=shots_rendered)},
            ],
        )
        characters = [
            Character(
                name=c.get("name", ""),
                description=c.get("description", ""),
                voice=c.get("voice", "neutral"),
            )
            for c in data.get("characters", [])
        ]
        return StyleBible(look=data.get("look", ""), characters=characters)

    @staticmethod
    def apply(bible: StyleBible, video_prompt: str) -> str:
        """Inject the cached look + character descriptions into a per-shot prompt."""
        char_desc = "; ".join(f"{c.name}: {c.description}" for c in bible.characters)
        parts = [video_prompt]
        if char_desc:
            parts.append(f"Characters — {char_desc}.")
        if bible.look:
            parts.append(f"Visual style — {bible.look}.")
        return " ".join(parts)
