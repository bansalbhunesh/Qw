#!/usr/bin/env python3
"""inject_bench.py — injects the latest benchmark report into the README.

Run after `python -m bench.benchmark` to update the benchmark table in
README.md automatically. Safe to re-run — it replaces the existing table.

Usage:
    python scripts/inject_bench.py                    # uses bench/results/report.md
    python scripts/inject_bench.py --report path.md   # use a custom report
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MARKER_START = "<!-- BENCH_START -->"
MARKER_END = "<!-- BENCH_END -->"


def inject(readme_path: Path, report_path: Path) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8", errors="replace")

    if "_(mock run)_" in report:
        print("ERROR: report.md is from a mock run (AUTEUR_MOCK=1).")
        print("  Mock scores are deterministic and meaningless — do NOT inject them into the README.")
        print("  Run the benchmark with a real API key to get genuine numbers, then re-run this script.")
        raise SystemExit(1)

    block = f"{MARKER_START}\n{report.strip()}\n{MARKER_END}"

    if MARKER_START in readme:
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
            re.DOTALL,
        )
        updated = pattern.sub(block, readme)
    else:
        # Insert before the ## Architecture section
        updated = readme.replace(
            "## Architecture",
            f"{block}\n\n## Architecture",
            1,
        )

    readme_path.write_text(updated, encoding="utf-8")
    print(f"Injected benchmark report from {report_path} into {readme_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inject benchmark results into README")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--report", default="bench/results/report.md")
    args = parser.parse_args(argv)

    readme_path = Path(args.readme)
    report_path = Path(args.report)

    if not readme_path.exists():
        print(f"ERROR: README not found: {readme_path}", file=sys.stderr)
        return 1
    if not report_path.exists():
        print(f"ERROR: Report not found: {report_path}", file=sys.stderr)
        print("Run: AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt", file=sys.stderr)
        return 1

    inject(readme_path, report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
