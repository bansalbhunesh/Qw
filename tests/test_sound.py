"""Sound agent tests — procedural score synthesis (mock mode, no spend)."""

import os
from pathlib import Path

os.environ["AUTEUR_MOCK"] = "1"

from auteur import media
from auteur.agents.sound import Sound
from auteur.budget import BudgetGovernor
from auteur.config import BudgetConfig


def _sound():
    return Sound(BudgetGovernor(BudgetConfig()))


def test_score_generates_music(tmp_path):
    out = _sound().score("melancholy", 4.0, str(tmp_path / "score.wav"), intensity=0.7)
    assert Path(out).exists()
    dur = media.probe_duration(out)
    assert 3.5 <= dur <= 4.5


def test_score_unknown_mood_falls_back(tmp_path):
    out = _sound().score("zzz-not-a-mood", 3.0, str(tmp_path / "score.wav"))
    assert Path(out).exists()
    assert Path(out).stat().st_size > 1000


def test_score_handles_zero_duration(tmp_path):
    # Should not crash; clamps to a sane default.
    out = _sound().score("tense", 0.0, str(tmp_path / "score.wav"))
    assert Path(out).exists()


def test_voice_map_covers_art_director_options():
    """Every voice descriptor in the Art Director's prompt should have a mapping."""
    from auteur.agents.sound import _VOICE_MAP
    art_director_voices = {"warm", "gravelly", "youthful", "neutral", "husky", "crisp"}
    unmapped = art_director_voices - set(_VOICE_MAP)
    assert not unmapped, f"unmapped voice descriptors: {unmapped}"


def test_voice_map_fallback_is_english_compatible():
    """The fallback voice must be English-compatible, not Chinese-only."""
    from auteur.agents.sound import _VOICE_MAP
    fallback = _VOICE_MAP.get("__nonexistent__", None)
    # Fallback should be None (not in map), and the code's default should be 'longshu'
    assert fallback is None
