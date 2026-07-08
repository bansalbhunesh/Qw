"""Benchmark harness smoke test (mock mode)."""

import os

os.environ["AUTEUR_MOCK"] = "1"

from bench.benchmark import run_benchmark, render_report  # noqa: E402


def test_benchmark_runs_both_systems_and_reports(tmp_path):
    premises = ["A kid trades his grandfather's watch and comes back to look at it daily"]
    results = run_benchmark(premises, tmp_path)

    systems = {r.system for r in results}
    assert systems == {"naive", "auteur"}
    assert all(r.tokens > 0 for r in results)

    report = render_report(results)
    assert "Headline" in report
    assert "Quality / 1k tok" in report
    # finals exist on disk
    assert (tmp_path / "auteur_0" / "final.mp4").exists()
    assert (tmp_path / "naive_0" / "final.mp4").exists()
