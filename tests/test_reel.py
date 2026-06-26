"""Demo reel generator test (mock mode — no spend)."""

import importlib.util
import os
from pathlib import Path

os.environ["AUTEUR_MOCK"] = "1"

import pytest

pil = pytest.importorskip("PIL", reason="Pillow required for reel generation")

_SPEC = importlib.util.spec_from_file_location(
    "make_reel", Path(__file__).resolve().parent.parent / "scripts" / "make_reel.py"
)
make_reel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(make_reel)


def _make_production(workdir):
    from auteur.agents.showrunner import Showrunner
    from auteur.config import ProductionConfig
    cfg = ProductionConfig(shots=2)
    cfg.budget.max_clips = 6
    Showrunner(cfg, workdir=workdir).run("A lighthouse keeper teaches the drone")


def test_reel_landscape(tmp_path):
    _make_production(tmp_path)
    out = make_reel.build(tmp_path, tmp_path / "reel.mp4", vertical=False)
    assert Path(out).exists() and Path(out).stat().st_size > 0
    from auteur import media
    assert media.has_audio_stream(out)


def test_reel_vertical(tmp_path):
    _make_production(tmp_path)
    out = make_reel.build(tmp_path, tmp_path / "reel_v.mp4", vertical=True)
    assert Path(out).exists() and Path(out).stat().st_size > 0


def test_font_resolution_never_crashes():
    """Font lookup must degrade gracefully when no system font is found."""
    assert make_reel._font_path(True) is None or isinstance(make_reel._font_path(True), str)


def test_wrap_helper():
    lines = make_reel._wrap("a b c d e f g h", 5)
    assert all(len(l) <= 6 for l in lines)
    assert " ".join(lines).split() == ["a", "b", "c", "d", "e", "f", "g", "h"]
