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


def test_manifest_includes_report_card(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A musician finds her stolen guitar in a pawn shop")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    rc = manifest.get("report_card", {})
    assert rc["shots_planned"] == 3
    assert rc["shots_rendered"] >= 1
    assert 0.0 <= rc["avg_critic_score"] <= 10.0
    assert rc["budget_utilization_pct"] > 0


def test_critic_scores_include_visual_continuity(tmp_path):
    """The 4-axis critic should produce visual_continuity scores."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A taxi driver picks up the passenger who ruined his life")
    scored = [s for s in prod.script.shots if s.critic_score is not None]
    assert len(scored) >= 3


def test_smart_voice_attribution():
    """Voice attribution should parse speaker tags and character names."""
    from auteur.agents.showrunner import Showrunner
    from auteur.models import Character, Production, Script, Shot, StyleBible

    chars = [
        Character(name="Mara", description="nurse", voice="warm"),
        Character(name="Elias", description="patient", voice="gravelly"),
    ]
    style = StyleBible(look="test", characters=chars)
    prod = Production(premise="test")
    prod.style = style

    # Strategy 1: explicit speaker tag
    shot_tagged = Shot(index=0, beat_index=0, description="test",
                       dialogue="Elias: I'm leaving today.", video_prompt="test",
                       importance=0.5)
    assert Showrunner._voice_for(prod, shot_tagged).name == "Elias"

    # Strategy 2: character name in description
    shot_desc = Shot(index=0, beat_index=0, description="Mara looks up from her chart",
                     dialogue="You'll be fine.", video_prompt="test", importance=0.5)
    assert Showrunner._voice_for(prod, shot_desc).name == "Mara"

    # Strategy 3: parity fallback
    shot_plain = Shot(index=1, beat_index=0, description="a hallway",
                      dialogue="Wait.", video_prompt="test", importance=0.5)
    assert Showrunner._voice_for(prod, shot_plain).name == "Elias"  # index 1 → char 1


def test_quality_gate_drops_low_scoring_shots(tmp_path):
    """Quality gate should drop below-threshold shots from the final cut."""
    cfg = _cfg(shots=4)
    cfg.quality_gate = 7.0
    show = Showrunner(cfg, workdir=tmp_path)
    prod = show.run("A painter watches the museum close for the last time")
    assert Path(prod.final_path).exists()


def test_naive_baseline_runs(tmp_path):
    naive = NaiveShowrunner(_cfg(shots=3), workdir=tmp_path)
    prod = naive.run("A street vendor and the regular who never speaks")
    assert Path(prod.final_path).exists()
    assert naive.governor.state.retakes_used == 0  # baseline never retakes
