"""The benchmark — the submission's kill shot.

Runs each premise through (a) the NAIVE baseline and (b) AUTEUR, scores both finished shorts
with the Qwen-VL rubric judge, and reports quality, tokens, and quality-per-token. The output
table goes straight into the README and the demo's closing slide.

Runs fully in mock mode (no key, no spend) to validate the harness; with a live key the same
code produces the real numbers.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from auteur.agents.showrunner import Showrunner
from auteur.baseline import NaiveShowrunner
from auteur.budget import BudgetGovernor
from auteur.config import ProductionConfig, is_mock
from auteur.llm import QwenClient
from auteur.agents.editor import Editor
from .rubric import RUBRIC_SYS, quality_per_token


@dataclass
class Result:
    premise: str
    system: str
    overall: float
    tokens: int
    clips: int
    retakes: int

    @property
    def quality_per_1k(self) -> float:
        return quality_per_token(self.overall, self.tokens)


def _judge(final_path: str) -> float:
    """Score a finished short with Qwen-VL using the shared rubric. Own budget (not charged
    to the production)."""
    gov = BudgetGovernor(ProductionConfig().budget)
    client = QwenClient(gov)
    editor = Editor(client, gov)
    frames = editor.sample_frames(final_path, n=4)
    content = [{"type": "text", "text": "Judge this short drama per the rubric."}]
    content += [{"type": "image_url", "image_url": {"url": u}} for u in frames]
    result = client.vision(
        "rubric_judge",
        [{"role": "system", "content": RUBRIC_SYS}, {"role": "user", "content": content}],
    )
    return float(result.get("overall", 0.0)) if isinstance(result, dict) else 0.0


def run_benchmark(premises: list[str], outdir: Path) -> list[Result]:
    results: list[Result] = []
    for i, premise in enumerate(premises):
        for system, cls in (("naive", NaiveShowrunner), ("auteur", Showrunner)):
            wd = outdir / f"{system}_{i}"
            show = cls(ProductionConfig(), workdir=wd)
            prod = show.run(premise)
            overall = _judge(prod.final_path)
            st = show.governor.state
            results.append(Result(
                premise=premise, system=system, overall=overall,
                tokens=st.tokens_used, clips=st.clips_used, retakes=st.retakes_used,
            ))
    return results


def render_report(results: list[Result]) -> str:
    lines = [
        "## Auteur benchmark — naive baseline vs. Auteur" + ("  _(mock run)_" if is_mock() else ""),
        "",
        "| Premise | System | Quality (0-10) | Tokens | Clips | Retakes | Quality / 1k tok |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.premise[:38]} | {r.system} | {r.overall:.1f} | {r.tokens:,} | "
            f"{r.clips} | {r.retakes} | {r.quality_per_1k:.2f} |"
        )
    lines += ["", _headline(results)]
    return "\n".join(lines)


def _headline(results: list[Result]) -> str:
    naive = [r for r in results if r.system == "naive"]
    auteur = [r for r in results if r.system == "auteur"]
    if not naive or not auteur:
        return ""

    def avg(rs, attr):
        return sum(getattr(r, attr) for r in rs) / len(rs)

    q_n, q_a = avg(naive, "overall"), avg(auteur, "overall")
    t_a = avg(auteur, "tokens")
    quality_gain = ((q_a - q_n) / q_n * 100) if q_n else 0
    budget_pct = (t_a / 120_000 * 100)
    return (
        f"**Headline:** Auteur scores **{q_a:.1f}/10** vs the baseline's **{q_n:.1f}/10** "
        f"— a **{quality_gain:.0f}% quality improvement** — "
        f"using just **{budget_pct:.1f}%** of the 120K token budget "
        f"({int(t_a):,} tokens). The Budget Governor ensures the extra investment goes to "
        f"critic-reviewed, importance-weighted shots with exactly one budgeted retake when a take fails."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auteur benchmark: naive vs Auteur")
    parser.add_argument("--premises", default="bench/premises.txt")
    parser.add_argument("--out", default="bench/results")
    parser.add_argument("--limit", type=int, default=0, help="cap number of premises (0 = all)")
    args = parser.parse_args(argv)

    premises = [l.strip() for l in Path(args.premises).read_text().splitlines() if l.strip()]
    if args.limit:
        premises = premises[: args.limit]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    results = run_benchmark(premises, outdir)
    report = render_report(results)
    (outdir / "report.md").write_text(report)
    (outdir / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
