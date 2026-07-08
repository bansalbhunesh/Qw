"""Tests for the Cinematographer's identity-lock conditioning ladder (r2v/kf2v/i2v/t2v).

These prove the escalation ordering, the per-mode DashScope payload fragments, budget
metering of the chosen mode, and graceful degradation — all at the mock/logic level, no
network. The default path (previous-frame continuity only) must stay i2v -> t2v so the
existing pipeline behaviour is unchanged.
"""
from __future__ import annotations

import types


from auteur.agents import cinematographer as cine
from auteur.agents.cinematographer import Cinematographer
from auteur.budget import BudgetConfig, BudgetGovernor


def _gov(tmp_path) -> BudgetGovernor:
    return BudgetGovernor(BudgetConfig(), ledger_path=tmp_path / "ledger.json")


def _dp(tmp_path) -> Cinematographer:
    return Cinematographer(_gov(tmp_path))


def _touch(tmp_path, name: str) -> str:
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n")  # enough to exist
    return str(p)


def _stub_upload(monkeypatch):
    """Make image upload deterministic: oss://ref/<filename>, no network."""
    from pathlib import Path
    monkeypatch.setattr(
        Cinematographer, "_upload_image",
        lambda self, p: f"oss://ref/{Path(p).name}",
    )


def test_default_ladder_is_i2v_then_t2v(tmp_path):
    """Regression guard: previous-frame continuity only must not change behaviour."""
    dp = _dp(tmp_path)
    ladder = dp._build_ladder(None, "https://cdn/frame.png", None, None)
    assert [r["mode"] for r in ladder] == ["i2v", "t2v"]
    assert ladder[0]["media"] == {"img_url": "https://cdn/frame.png"}


def test_no_reference_ladder_is_t2v_only(tmp_path):
    dp = _dp(tmp_path)
    ladder = dp._build_ladder(None, None, None, None)
    assert [r["mode"] for r in ladder] == ["t2v"]


def test_full_escalation_ordering(tmp_path, monkeypatch):
    """identity ref + first/last frames + prev frame -> r2v > kf2v > i2v > t2v."""
    _stub_upload(monkeypatch)
    dp = _dp(tmp_path)
    ladder = dp._build_ladder(
        reference_image=_touch(tmp_path, "prev.png"),
        image_url=None,
        identity_reference=_touch(tmp_path, "hero.png"),
        end_reference_image=_touch(tmp_path, "end.png"),
    )
    assert [r["mode"] for r in ladder] == ["r2v", "kf2v", "i2v", "t2v"]


def test_per_mode_media_fragments(tmp_path, monkeypatch):
    """Each rung carries exactly the DashScope input keys that mode requires."""
    _stub_upload(monkeypatch)
    dp = _dp(tmp_path)
    ladder = dp._build_ladder(
        reference_image=_touch(tmp_path, "prev.png"),
        image_url=None,
        identity_reference=_touch(tmp_path, "hero.png"),
        end_reference_image=_touch(tmp_path, "end.png"),
    )
    by_mode = {r["mode"]: r["media"] for r in ladder}
    assert by_mode["r2v"] == {"ref_images_url": ["oss://ref/hero.png"]}
    assert by_mode["kf2v"] == {"first_frame_url": "oss://ref/prev.png",
                               "last_frame_url": "oss://ref/end.png"}
    assert by_mode["i2v"] == {"img_url": "oss://ref/prev.png"}
    assert by_mode["t2v"] == {}


def test_mock_render_meters_primary_mode(tmp_path, monkeypatch):
    """In mock mode the ledger records the strongest available mode as the clip's model."""
    monkeypatch.setenv("AUTEUR_MOCK", "1")
    _stub_upload(monkeypatch)
    dp = _dp(tmp_path)
    out = dp.render(
        "a hero turns to camera", tmp_path / "shot_0.mp4", index=0,
        identity_reference=_touch(tmp_path, "hero.png"),
    )
    assert out
    videos = [e for e in dp.governor.entries if e.kind == "video"]
    assert len(videos) == 1
    assert videos[0].model == "mock-wan-r2v"
    assert "r2v" in videos[0].note


def test_create_task_merges_media_and_sets_oss_header(tmp_path, monkeypatch):
    """_create_task puts conditioning inputs into `input` and flags oss:// resolution."""
    monkeypatch.setenv("AUTEUR_MOCK", "0")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        captured["headers"] = headers
        return types.SimpleNamespace(
            status_code=200, text="",
            json=lambda: {"output": {"task_id": "task-123"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(cine.requests, "post", fake_post)
    dp = _dp(tmp_path)
    task_id = dp._create_task(
        "wan2.7-r2v", "a hero", media={"ref_images_url": ["oss://ref/hero.png"]},
    )
    assert task_id == "task-123"
    assert captured["json"]["input"]["ref_images_url"] == ["oss://ref/hero.png"]
    assert captured["json"]["input"]["prompt"] == "a hero"
    assert captured["headers"].get("X-DashScope-OssResourceResolve") == "enable"


def test_has_oss_helper():
    assert cine._has_oss("oss://b/k")
    assert cine._has_oss(["https://x", "oss://b/k"])
    assert not cine._has_oss("https://x")
    assert not cine._has_oss([])
    assert not cine._has_oss(None)
