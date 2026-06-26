"""End-to-end pipeline smoke tests (mock mode — no key, no spend)."""

import os
from pathlib import Path

import pytest

# Force mock mode for the whole module.
os.environ["AUTEUR_MOCK"] = "1"

from auteur.agents.showrunner import Showrunner   # noqa: E402
from auteur.baseline import NaiveShowrunner        # noqa: E402
from auteur.config import ProductionConfig         # noqa: E402


def _cfg(shots=3):
    cfg = ProductionConfig(shots=shots)
    cfg.budget.max_clips = 12
    return cfg


def test_auteur_produces_a_real_mp4(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A lighthouse keeper teaches the drone sent to replace him")

    final = Path(prod.final_path)
    assert final.exists() and final.stat().st_size > 0
    assert prod.script is not None and len(prod.script.shots) == 3
    assert prod.style is not None and prod.style.characters
    # ledger written + tokens metered
    assert (tmp_path / "ledger.json").exists()
    assert show.governor.state.tokens_used > 0
    assert show.governor.state.clips_used >= 3


def test_every_shot_gets_a_critic_score(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("Two rival food-truck owners share one generator in a blackout")
    assert all(s.critic_score is not None for s in prod.script.shots)


def test_budget_governor_caps_clip_count(tmp_path):
    cfg = _cfg(shots=6)
    cfg.budget.max_clips = 2  # hard cap below shot count
    show = Showrunner(cfg, workdir=tmp_path)
    prod = show.run("A woman receives her own voicemails from a number that doesn't exist")
    assert show.governor.state.clips_used <= 2
    assert Path(prod.final_path).exists()  # ships what it has


def test_consistency_mode_produces_anchor_frames(tmp_path):
    cfg = _cfg(shots=3)
    cfg.consistency = True
    show = Showrunner(cfg, workdir=tmp_path)
    prod = show.run("A clockmaker races to finish a watch before dawn")
    assert Path(prod.final_path).exists()
    # Anchor frames are extracted from each shot to seed the next (visual continuity).
    anchors = list(Path(tmp_path).glob("anchor_*.png"))
    assert anchors, "expected at least one anchor frame in consistency mode"


def test_production_is_scored(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A diver finds a message in a bottle on the seafloor")
    assert Path(prod.final_path).exists()
    # A music bed was synthesized and a score plan recorded in the manifest.
    assert (tmp_path / "score.wav").exists()
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["score"].get("mood")


def test_voice_failure_does_not_discard_clip(tmp_path):
    """A TTS failure must never throw away an already-rendered clip."""
    from unittest.mock import patch
    cfg = _cfg(shots=3)
    show = Showrunner(cfg, workdir=tmp_path)
    with patch.object(show.sound, "voice_line", side_effect=RuntimeError("TTS down")):
        prod = show.run("An engineer finds music in a broken radio")
    assert Path(prod.final_path).exists()
    assert show.governor.state.clips_used >= 3


def test_naive_baseline_runs(tmp_path):
    naive = NaiveShowrunner(_cfg(shots=3), workdir=tmp_path)
    prod = naive.run("A street vendor and the regular who never speaks")
    assert Path(prod.final_path).exists()
    assert naive.governor.state.retakes_used == 0  # baseline never retakes
