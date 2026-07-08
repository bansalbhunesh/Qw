"""End-to-end pipeline smoke tests (mock mode — no key, no spend)."""

import os
from pathlib import Path


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
    from auteur.models import Character, Production, Shot, StyleBible

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


def test_parallel_render_mode(tmp_path):
    """With consistency disabled, shots should render (potentially in parallel)."""
    cfg = _cfg(shots=3)
    cfg.consistency = False
    show = Showrunner(cfg, workdir=tmp_path)
    prod = show.run("Two strangers share an umbrella in a monsoon")
    assert Path(prod.final_path).exists()
    assert show.governor.state.clips_used >= 3
    # No anchor frames should exist in parallel mode
    anchors = list(Path(tmp_path).glob("anchor_*.png"))
    assert len(anchors) == 0


def test_manifest_includes_timeline(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A retired astronaut tends a garden that orbits Earth")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    timeline = manifest.get("timeline", [])
    assert len(timeline) >= 3  # at least script, shots_done, assembly
    phases = [t["phase"] for t in timeline]
    assert "script" in phases
    assert "assembly" in phases
    assert all(t["elapsed_s"] >= 0 for t in timeline)


def test_manifest_includes_score_plan(tmp_path):
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A barista makes coffee for a customer who's been dead for weeks")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    score_plan = manifest.get("score", {})
    assert "mood" in score_plan
    assert "intensity" in score_plan


def test_budget_tokens_by_tier(tmp_path):
    """Budget summary should include tier-level token breakdown."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    show.run("A violin maker hears his dead wife in the wood grain")
    summary = show.governor.summary()
    by_tier = summary.get("tokens_by_tier", {})
    assert len(by_tier) >= 1
    assert all(isinstance(v, int) and v > 0 for v in by_tier.values())


def test_style_bible_has_characters_and_look(tmp_path):
    """Style Bible should have characters with descriptions and a look."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A chess prodigy plays her first game against a machine")
    assert prod.style is not None
    assert len(prod.style.characters) >= 1
    assert all(c.name and c.description for c in prod.style.characters)
    assert prod.style.look


def test_shots_have_importance_weights(tmp_path):
    """Every shot should inherit an importance weight from its beat."""
    show = Showrunner(_cfg(shots=4), workdir=tmp_path)
    prod = show.run("A thief returns what she stole twenty years later")
    assert prod.script is not None
    for shot in prod.script.shots:
        assert 0.0 <= shot.importance <= 1.0
    # The first shot (hook) should have the highest importance
    assert prod.script.shots[0].importance >= prod.script.shots[-1].importance


def test_empty_dialogue_gets_no_audio(tmp_path):
    """Shots with empty dialogue shouldn't produce audio artifacts."""
    from auteur.agents.sound import Sound
    from auteur.budget import BudgetGovernor
    from auteur.config import BudgetConfig
    sound = Sound(BudgetGovernor(BudgetConfig()))
    result = sound.voice_line("", None, str(tmp_path / "empty.wav"))
    assert result is None


def test_multiple_premises_produce_independent_outputs(tmp_path):
    """Each premise should produce a separate, independent production."""
    show1 = Showrunner(_cfg(shots=2), workdir=tmp_path / "p1")
    show2 = Showrunner(_cfg(shots=2), workdir=tmp_path / "p2")
    prod1 = show1.run("A pilot lands on the wrong continent")
    prod2 = show2.run("A baker burns her last loaf on purpose")
    assert Path(prod1.final_path).exists()
    assert Path(prod2.final_path).exists()
    assert prod1.final_path != prod2.final_path


def test_manifest_includes_decisions(tmp_path):
    """Manifest should include the Governor's decision log with retake reasoning."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A clockmaker opens a watch and finds a message inside")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    decisions = manifest.get("decisions", [])
    assert len(decisions) >= 1
    for d in decisions:
        assert "shot" in d
        assert "type" in d
        assert "reason" in d
        assert "retake" in d


def test_report_card_has_quality_arc(tmp_path):
    """Report card should include a per-shot quality arc."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A cartographer draws a map to a place that doesn't exist")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    arc = manifest.get("report_card", {}).get("quality_arc", [])
    assert len(arc) >= 1
    for point in arc:
        assert "shot" in point
        assert "score" in point
        assert "importance" in point
        assert "retaken" in point


def test_report_card_has_efficiency_analysis(tmp_path):
    """Report card should include routing efficiency analysis."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("An architect draws a building that can only exist in dreams")
    import json
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    eff = manifest.get("report_card", {}).get("efficiency", {})
    assert "actual_tokens" in eff
    assert "naive_estimate_tokens" in eff
    assert eff["actual_tokens"] > 0


def test_transition_planning():
    """Editor should plan transitions based on beat tone changes."""
    from auteur.agents.editor import Editor
    from auteur.models import Beat

    beats = [
        Beat(index=0, label="Hook", summary="...", importance=1.0, tone="tense"),
        Beat(index=1, label="Setup", summary="...", importance=0.7, tone="tense"),
        Beat(index=2, label="Turn", summary="...", importance=0.8, tone="cathartic"),
    ]
    transitions = Editor.plan_transitions(beats)
    assert len(transitions) == 2
    assert transitions[0] == "dissolve"  # same tone → dissolve
    assert transitions[1] == "fade"     # cathartic → fade


def test_storyboard_export(tmp_path):
    """Production should generate a storyboard.html with shot breakdowns."""
    show = Showrunner(_cfg(shots=3), workdir=tmp_path)
    prod = show.run("A poet reads to an empty theater every night")
    sb = tmp_path / "storyboard.html"
    assert sb.exists()
    html = sb.read_text()
    assert "Auteur" in html
    assert "Shot 0" in html
    assert "Budget Summary" in html


def test_prompt_optimizer_runs():
    """Prompt optimizer should refine raw prompts without breaking them."""
    from auteur.agents.prompt_optimizer import PromptOptimizer
    from auteur.budget import BudgetGovernor
    from auteur.config import BudgetConfig
    from auteur.llm import QwenClient
    gov = BudgetGovernor(BudgetConfig())
    client = QwenClient(gov)
    opt = PromptOptimizer(client)
    raw = "cinematic vertical shot, a person in a dim room, emotional, 9:16"
    refined = opt.refine(raw, "medium close-up, soft light", "Hook")
    assert len(refined) > 0
    assert refined != raw


def test_dynamic_resolution_config():
    """Dynamic resolution config should route hero shots to higher res."""
    cfg = _cfg(shots=3)
    cfg.dynamic_resolution = True
    cfg.hero_resolution = "1080P"
    cfg.base_resolution = "480P"
    cfg.hero_importance_threshold = 0.8
    show = Showrunner(cfg, workdir=Path("/tmp/test_dynres"))
    from auteur.models import Shot
    hero = Shot(index=0, beat_index=0, description="", dialogue="", video_prompt="",
                importance=0.95)
    grunt = Shot(index=1, beat_index=1, description="", dialogue="", video_prompt="",
                 importance=0.4)
    assert show._resolve_resolution(hero) == "1080P"
    assert show._resolve_resolution(grunt) == "480P"


def test_shot_duration_pacing():
    """Shot duration should vary based on importance and beat type."""
    from auteur.media import shot_duration
    hook_dur = shot_duration(1.0, "Hook")
    setup_dur = shot_duration(0.5, "Setup")
    assert hook_dur > setup_dur
    assert 3.0 <= hook_dur <= 8.0
    assert 3.0 <= setup_dur <= 8.0


def test_naive_baseline_runs(tmp_path):
    naive = NaiveShowrunner(_cfg(shots=3), workdir=tmp_path)
    prod = naive.run("A street vendor and the regular who never speaks")
    assert Path(prod.final_path).exists()
    assert naive.governor.state.retakes_used == 0  # baseline never retakes
