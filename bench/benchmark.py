"""The benchmark — the submission's kill shot.

Runs each premise through (a) a NAIVE baseline showrunner and (b) AUTEUR, scores both finished
shorts with the Qwen-VL rubric, and reports quality, tokens, and quality-per-token. The output
table goes straight into the README and the demo's closing slide.

The naive baseline is deliberately the "obvious" build everyone else ships: one-shot script,
qwen-max for everything, render every shot once, no critic, no budget routing, no caching.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    premise: str
    system: str
    overall: float
    tokens: int

    @property
    def quality_per_1k(self) -> float:
        return self.overall / (self.tokens / 1000.0) if self.tokens else 0.0


def run_benchmark(premises: list[str], outdir: Path) -> list[Result]:
    """Produce + judge both systems for every premise.

    Implementation note: this orchestrates real productions, so it is gated on live DashScope
    access and is run during the build to populate the README table. The structure below is the
    contract the report renderer expects.
    """
    from .rubric import RUBRIC_SYS  # noqa: F401  (used once productions are wired in)

    results: list[Result] = []
    # for premise in premises:
    #     naive = NaiveShowrunner(...).run(premise)   # baseline build
    #     auteur = Showrunner(...).run(premise)        # our build
    #     score each final cut with Qwen-VL using RUBRIC_SYS
    #     results.append(Result(...)) for both
    return results


def render_report(results: list[Result]) -> str:
    """Render a Markdown table + the headline efficiency claim."""
    lines = ["| Premise | System | Quality (0-10) | Tokens | Quality / 1k tok |",
             "|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.premise[:40]} | {r.system} | {r.overall:.1f} | {r.tokens:,} | {r.quality_per_1k:.2f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auteur benchmark: naive vs Auteur")
    parser.add_argument("--premises", default="bench/premises.txt")
    parser.add_argument("--out", default="bench/results")
    args = parser.parse_args(argv)

    premises = [l.strip() for l in Path(args.premises).read_text().splitlines() if l.strip()]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    results = run_benchmark(premises, outdir)
    report = render_report(results)
    (outdir / "report.md").write_text(report)
    (outdir / "results.json").write_text(
        json.dumps([r.__dict__ for r in results], indent=2)
    )
    print(report or "(no results yet — wire DASHSCOPE_API_KEY and run live)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
