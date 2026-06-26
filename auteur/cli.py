"""Command-line entrypoint: `python -m auteur.cli "<premise>"`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import log as _logmod
from .config import ProductionConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auteur — the budget-aware AI showrunner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python -m auteur.cli 'A lighthouse keeper teaches the drone sent to replace him'",
    )
    parser.add_argument("premise", help="one-line premise for the short drama")
    parser.add_argument("--shots", type=int, default=6, help="number of shots (default: 6)")
    parser.add_argument("--max-tokens", type=int, default=120_000, help="token budget ceiling")
    parser.add_argument("--max-clips", type=int, default=8, help="clip render budget")
    parser.add_argument("--max-retakes", type=int, default=4, help="retake budget")
    parser.add_argument(
        "--max-spend-usd", type=float, default=2.00,
        help="hard real-money ceiling on video renders in USD (default: 2.00)",
    )
    parser.add_argument("--resolution", default="720P", choices=["480P", "720P", "1080P"],
                        help="Wan render resolution (default: 720P)")
    parser.add_argument("--out", default="out", help="output directory")
    parser.add_argument(
        "--no-consistency", action="store_true",
        help="disable image-to-video continuity (render every shot independently)",
    )
    parser.add_argument(
        "--estimate", action="store_true",
        help="print the projected cost of this production and exit (renders nothing)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    import logging
    _logmod.setup(logging.DEBUG if args.verbose else logging.INFO)
    _log = _logmod.get("cli")

    cfg = ProductionConfig(shots=args.shots, resolution=args.resolution,
                           consistency=not args.no_consistency)
    cfg.budget.max_tokens = args.max_tokens
    cfg.budget.max_clips = args.max_clips
    cfg.budget.max_retakes = args.max_retakes
    cfg.budget.max_spend_usd = args.max_spend_usd

    from .config import clip_price_usd

    if args.estimate:
        price = clip_price_usd(cfg.resolution)
        by_cost = int(args.max_spend_usd // price) if price > 0 else args.max_clips
        cap = min(args.max_clips, by_cost)
        worst = min(args.shots + args.max_retakes, cap)
        print("Cost estimate (no clips will be rendered):")
        print(f"  resolution        : {cfg.resolution}")
        print(f"  price per clip    : ${price:.2f}")
        print(f"  spend cap         : ${args.max_spend_usd:.2f}")
        print(f"  effective max clips: {cap}  (count cap {args.max_clips}, cost cap {by_cost})")
        print(f"  planned shots     : {args.shots}  (+{args.max_retakes} possible retakes)")
        print(f"  worst-case cost   : ${worst * price:.2f}  ({worst} clips)")
        print(f"  best-case cost    : ${min(args.shots, cap) * price:.2f}  (no retakes)")
        if cap < args.shots:
            print(f"  ⚠  spend cap limits you to {cap} clips — fewer than {args.shots} shots.")
        return 0

    from .agents.showrunner import Showrunner

    show = Showrunner(cfg, workdir=args.out)

    try:
        prod = show.run(args.premise)
    except Exception as exc:
        _log.error("production failed: %s", exc)
        show.governor.flush()
        return 1

    print(f"\nFinal cut: {prod.final_path}")
    print(f"Manifest:  {Path(args.out) / 'manifest.json'}")
    print(f"Ledger:    {Path(args.out) / 'ledger.json'}")
    print("\nBudget summary:")
    print(json.dumps(show.governor.summary(), indent=2))

    if prod.script:
        print(f"\nShots ({len(prod.script.shots)}):")
        for s in prod.script.shots:
            flag = " [retaken]" if s.retaken else ""
            score = f" score={s.critic_score:.1f}" if s.critic_score is not None else ""
            print(f"  {s.index}. [{s.importance:.1f}]{score}{flag}  {s.description[:60]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
