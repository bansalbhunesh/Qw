"""Command-line entrypoint: `python -m auteur.cli "<premise>"`."""

from __future__ import annotations

import argparse
import json
import sys

from .config import ProductionConfig
from .agents.showrunner import Showrunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auteur — the budget-aware AI showrunner")
    parser.add_argument("premise", help="one-line premise for the short drama")
    parser.add_argument("--shots", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=120_000)
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)

    cfg = ProductionConfig(shots=args.shots)
    cfg.budget.max_tokens = args.max_tokens

    show = Showrunner(cfg, workdir=args.out)
    prod = show.run(args.premise)

    print(f"\n🎬 Final cut: {prod.final_path}")
    print("📒 Budget ledger:")
    print(json.dumps(show.governor.summary(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
