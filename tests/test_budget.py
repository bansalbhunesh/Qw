"""Budget Governor economics — the heart of the 'quality under a token budget' claim."""

from auteur.budget import BudgetExceeded, BudgetGovernor
from auteur.config import BudgetConfig, Tier

import pytest


def make_gov(**kw):
    return BudgetGovernor(BudgetConfig(**kw))


def test_token_metering_accumulates():
    gov = make_gov()
    gov.record_llm("writer", "qwen-max", Tier.CREATIVE, 100, 50)
    gov.record_llm("critic", "qwen-vl-max", Tier.VISION, 30, 10)
    assert gov.state.tokens_used == 190
    assert gov.summary()["tokens_by_stage"] == {"writer": 150, "critic": 40}


def test_token_gate_blocks_overspend():
    gov = make_gov(max_tokens=100)
    gov.record_llm("writer", "qwen-max", Tier.CREATIVE, 80, 0)
    with pytest.raises(BudgetExceeded):
        gov.assert_can_spend_tokens(50)


def test_clip_budget_caps_renders():
    gov = make_gov(max_clips=2)
    assert gov.can_render_clip()
    gov.record_video("dp", "wan", clips=2)
    assert not gov.can_render_clip()


def test_spend_cap_stops_renders_before_count_cap():
    # $0.20/clip, $0.50 cap -> only 2 clips allowed even though count cap is 8.
    gov = make_gov(max_clips=8, max_spend_usd=0.50, clip_price_usd=0.20)
    assert gov.clip_cap() == 2
    assert gov.can_render_clip()
    gov.record_video("dp", "wan", clips=1)
    assert gov.can_render_clip()
    gov.record_video("dp", "wan", clips=1)
    assert not gov.can_render_clip()  # 3rd clip would be $0.60 > $0.50
    assert gov.estimated_cost_usd == 0.40


def test_count_cap_governs_when_pricing_unset():
    # No clip price (mock) -> dollar cap is inert, count cap governs.
    gov = make_gov(max_clips=3, max_spend_usd=0.10, clip_price_usd=0.0)
    assert gov.clip_cap() == 3
    gov.record_video("dp", "wan", clips=3)
    assert not gov.can_render_clip()
    assert gov.estimated_cost_usd == 0.0


def test_retake_only_for_important_failing_shots():
    gov = make_gov(max_retakes=2, pass_threshold=7.0, hook_priority_percentile=0.75)
    # passing shot -> never retake
    assert not gov.should_retake(critic_score=8.0, shot_importance=1.0)
    # failing but unimportant -> skip the reshoot, save budget
    assert not gov.should_retake(critic_score=5.0, shot_importance=0.3)
    # failing AND important -> worth a reshoot
    assert gov.should_retake(critic_score=5.0, shot_importance=0.9)


def test_retake_budget_is_finite():
    gov = make_gov(max_retakes=1)
    assert gov.should_retake(5.0, 0.9)
    gov.register_retake()
    assert not gov.should_retake(5.0, 0.9)


def test_ledger_flush_roundtrip(tmp_path):
    gov = BudgetGovernor(BudgetConfig(), ledger_path=tmp_path / "ledger.json")
    gov.record_llm("writer", "qwen-max", Tier.CREATIVE, 10, 5)
    gov.record_video("dp", "wan", clips=1)
    gov.flush()
    import json

    data = json.loads((tmp_path / "ledger.json").read_text())
    assert data["summary"]["tokens_used"] == 15
    assert len(data["entries"]) == 2


def test_tokens_by_tier():
    gov = make_gov()
    gov.record_llm("writer", "qwen-max", Tier.CREATIVE, 100, 50)
    gov.record_llm("composer", "qwen-flash", Tier.GRUNT, 20, 10)
    gov.record_llm("critic", "qwen-vl-max", Tier.VISION, 50, 30)
    by_tier = gov.summary()["tokens_by_tier"]
    assert by_tier == {"creative": 150, "grunt": 30, "vision": 80}


def test_tts_entries_tracked():
    gov = make_gov()
    gov.record_tts("sound", "cosyvoice", note="test line")
    assert len(gov.entries) == 1
    assert gov.entries[0].kind == "tts"
    assert gov.state.tokens_used == 0  # TTS doesn't count against token budget


def test_multiple_flushes_overwrite(tmp_path):
    gov = BudgetGovernor(BudgetConfig(), ledger_path=tmp_path / "ledger.json")
    gov.record_llm("writer", "qwen-max", Tier.CREATIVE, 10, 5)
    gov.flush()
    gov.record_llm("critic", "qwen-vl-max", Tier.VISION, 20, 10)
    gov.flush()
    import json
    data = json.loads((tmp_path / "ledger.json").read_text())
    assert data["summary"]["tokens_used"] == 45
    assert len(data["entries"]) == 2


def test_clip_cap_minimum_of_count_and_cost():
    gov = make_gov(max_clips=10, max_spend_usd=0.50, clip_price_usd=0.20)
    assert gov.clip_cap() == 2  # cost cap is tighter
    gov2 = make_gov(max_clips=2, max_spend_usd=5.00, clip_price_usd=0.20)
    assert gov2.clip_cap() == 2  # count cap is tighter
