"""Sound — dialogue voicing via DashScope TTS (CosyVoice), plus music/SFX cues.

Each shot's dialogue is voiced with a per-character voice from the Style Bible. TTS calls are
metered so the ledger reflects audio spend. In mock mode we emit a short placeholder tone so the
path is exercised without spend.
"""

from __future__ import annotations

from pathlib import Path

from ..budget import BudgetGovernor
from ..config import TTS_MODEL, is_mock
from ..models import Character
from .. import media

STAGE = "sound"


class Sound:
    def __init__(self, governor: BudgetGovernor):
        self.governor = governor

    def voice_line(self, text: str, character: Character | None, out_path: str) -> str | None:
        """Synthesize one dialogue line to an audio file; return its path (or None if no line)."""
        if not text.strip():
            return None

        if is_mock():
            self._mock_tone(out_path)
            self.governor.record_tts(STAGE, "mock-tts", note=text[:60])
            return out_path

        # TODO(build): call DashScope CosyVoice synthesis and write bytes to out_path.
        self.governor.record_tts(STAGE, TTS_MODEL, note=text[:60])
        return out_path

    @staticmethod
    def _mock_tone(out_path: str) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        media._run([  # short sine as a stand-in for a voiced line
            "-f", "lavfi", "-i", "sine=frequency=330:duration=1.5",
            "-c:a", "pcm_s16le", str(out),
        ])
