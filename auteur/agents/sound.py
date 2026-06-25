"""Sound — dialogue voicing via DashScope TTS (CosyVoice), plus music/SFX cues.

Each shot's dialogue is voiced with a per-character voice from the Style Bible. Music is
selected as a cue (genre/mood) the editor can lay under the cut. TTS calls are metered so the
ledger reflects audio spend too.
"""

from __future__ import annotations

from ..budget import BudgetGovernor
from ..config import TTS_MODEL
from ..models import Character

STAGE = "sound"


class Sound:
    def __init__(self, governor: BudgetGovernor):
        self.governor = governor

    def voice_line(self, text: str, character: Character | None, out_path: str) -> str | None:
        """Synthesize one dialogue line to an audio file; return its path (or None if no line).

        DashScope TTS (CosyVoice) async job — wired in during the build once keys are present.
        """
        if not text.strip():
            return None
        # TODO(build): call DashScope CosyVoice synthesis, write bytes to out_path.
        self.governor.record_tts(STAGE, TTS_MODEL, note=text[:60])
        return out_path
