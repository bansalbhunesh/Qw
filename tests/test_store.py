"""Tests for the SQLite ProductionStore — the queryable persistence layer."""
from __future__ import annotations

from auteur.store import ProductionStore


def _summary(**kw):
    base = {
        "tokens_used": 10000, "token_budget": 120000, "clips_used": 8,
        "retakes_used": 2, "estimated_cost_usd": 0.60,
    }
    base.update(kw)
    return base


def _entries():
    return [
        {"ts": 1.0, "stage": "writer", "kind": "llm", "model": "qwen-max",
         "tier": "creative", "prompt_tokens": 400, "completion_tokens": 200, "clips": 0, "note": ""},
        {"ts": 2.0, "stage": "prompt_opt", "kind": "llm", "model": "qwen-flash",
         "tier": "grunt", "prompt_tokens": 100, "completion_tokens": 50, "clips": 0, "note": ""},
        {"ts": 3.0, "stage": "cinematographer", "kind": "video", "model": "mock-wan-t2v",
         "tier": None, "prompt_tokens": 0, "completion_tokens": 0, "clips": 1, "note": "t2v"},
        {"ts": 4.0, "stage": "cinematographer", "kind": "video", "model": "mock-wan-r2v",
         "tier": None, "prompt_tokens": 0, "completion_tokens": 0, "clips": 1, "note": "r2v"},
        {"ts": 5.0, "stage": "cinematographer", "kind": "video", "model": "mock-wan-r2v",
         "tier": None, "prompt_tokens": 0, "completion_tokens": 0, "clips": 1, "note": "r2v"},
    ]


def test_save_and_list_roundtrip(tmp_path):
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "a nurse finds a note", _summary(), _entries(),
                          report_card={"avg_critic_score": 7.3}, final_path="p1/final.mp4")
    prods = store.list_productions()
    assert len(prods) == 1
    assert prods[0]["id"] == "p1"
    assert prods[0]["premise"] == "a nurse finds a note"
    assert prods[0]["avg_critic_score"] == 7.3
    assert prods[0]["tokens_used"] == 10000


def test_ledger_roundtrip(tmp_path):
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", _summary(), _entries())
    led = store.ledger_for("p1")
    assert len(led) == 5
    assert led[0]["stage"] == "writer"
    assert led[0]["prompt_tokens"] == 400


def test_aggregate_across_productions(tmp_path):
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", _summary(tokens_used=10000, estimated_cost_usd=0.60),
                          _entries(), report_card={"avg_critic_score": 7.0})
    store.save_production("p2", "y", _summary(tokens_used=6000, estimated_cost_usd=0.40),
                          _entries(), report_card={"avg_critic_score": 8.0})
    agg = store.aggregate()
    assert agg["productions"] == 2
    assert agg["total_tokens"] == 16000
    assert agg["total_cost_usd"] == 1.0
    assert agg["avg_score"] == 7.5


def test_tokens_by_model(tmp_path):
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", _summary(), _entries())
    tbm = {r["model"]: r["tokens"] for r in store.tokens_by_model()}
    assert tbm["qwen-max"] == 600
    assert tbm["qwen-flash"] == 150
    assert "mock-wan-t2v" not in tbm  # video entries excluded from llm token totals


def test_conditioning_modes_distribution(tmp_path):
    """The store surfaces the r2v/i2v/t2v mode mix — the pipeline conditioning ladder in data."""
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", _summary(), _entries())
    modes = {r["model"]: r["clips"] for r in store.conditioning_modes()}
    assert modes["mock-wan-r2v"] == 2
    assert modes["mock-wan-t2v"] == 1


def test_resave_is_idempotent(tmp_path):
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", _summary(), _entries())
    store.save_production("p1", "x updated", _summary(), _entries())
    prods = store.list_productions()
    assert len(prods) == 1
    assert prods[0]["premise"] == "x updated"
    assert len(store.ledger_for("p1")) == 5  # not doubled


def test_accepts_ledger_objects(tmp_path):
    """save_production accepts real LedgerEntry objects, not just dicts."""
    from auteur.budget import BudgetConfig, BudgetGovernor
    gov = BudgetGovernor(BudgetConfig())
    gov.record_video("cinematographer", "mock-wan-r2v", clips=1, note="r2v")
    store = ProductionStore(tmp_path / "t.db")
    store.save_production("p1", "x", gov.summary(), gov.entries)
    assert store.conditioning_modes()[0]["model"] == "mock-wan-r2v"
