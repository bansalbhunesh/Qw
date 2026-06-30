"""Command-line entrypoint: `python -m auteur.cli "<premise>"`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import log as _logmod
from .config import ProductionConfig


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, configure the production, and run the Showrunner."""
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
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"],
                        help="Wan render aspect ratio (default: 9:16)")
    parser.add_argument("--out", default="out", help="output directory")
    parser.add_argument(
        "--no-consistency", action="store_true",
        help="disable image-to-video continuity and enable parallel rendering",
    )
    parser.add_argument(
        "--quality-gate", type=float, default=0.0, metavar="SCORE",
        help="drop shots scoring below this threshold from the final cut (0 = keep all)",
    )
    parser.add_argument(
        "--dynamic-resolution", action="store_true",
        help="render hero shots at 1080P and others at 480P (budget-optimized quality)",
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
                           aspect_ratio=args.aspect_ratio,
                           consistency=not args.no_consistency,
                           quality_gate=args.quality_gate,
                           dynamic_resolution=args.dynamic_resolution)
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

    summary = show.governor.summary()

    print(f"\n{'=' * 60}")
    print("  PRODUCTION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Final cut  : {prod.final_path}")
    print(f"  Storyboard : {Path(args.out) / 'storyboard.html'}")
    print(f"  Manifest   : {Path(args.out) / 'manifest.json'}")
    print(f"  Ledger     : {Path(args.out) / 'ledger.json'}")

    print("\n  Budget:")
    pct = summary['tokens_used'] / max(1, summary['token_budget']) * 100
    print(f"    Tokens  : {summary['tokens_used']:,} / {summary['token_budget']:,}  ({pct:.1f}%)")
    print(f"    Clips   : {summary['clips_used']} / {summary['clip_budget']}")
    print(f"    Retakes : {summary['retakes_used']} / {summary['retake_budget']}")
    if summary.get('estimated_cost_usd', 0) > 0:
        print(f"    Spend   : ${summary['estimated_cost_usd']:.2f} / ${summary['max_spend_usd']:.2f}")

    if summary.get('tokens_by_stage'):
        print("\n  Token breakdown by stage:")
        for stage, tokens in sorted(summary['tokens_by_stage'].items(),
                                    key=lambda x: -x[1]):
            bar = '#' * max(1, int(tokens / max(1, summary['tokens_used']) * 30))
            print(f"    {stage:16s}  {tokens:>6,}  {bar}")

    if summary.get('tokens_by_tier'):
        print("\n  Token breakdown by tier (model routing):")
        tier_names = {'grunt': 'qwen-flash', 'creative': 'qwen-max', 'vision': 'qwen-vl-max'}
        for tier, tokens in sorted(summary['tokens_by_tier'].items(),
                                   key=lambda x: -x[1]):
            model = tier_names.get(tier, tier)
            bar = '#' * max(1, int(tokens / max(1, summary['tokens_used']) * 30))
            print(f"    {tier:10s} ({model:12s})  {tokens:>6,}  {bar}")

    if prod.script:
        scored = [s for s in prod.script.shots if s.critic_score is not None]
        if scored:
            avg = sum(s.critic_score for s in scored) / len(scored)
            lo = min(s.critic_score for s in scored)
            hi = max(s.critic_score for s in scored)
            print(f"\n  Quality: avg={avg:.1f}  min={lo:.1f}  max={hi:.1f}")

        print("\n  Quality arc:")
        for s in prod.script.shots:
            if s.critic_score is not None:
                bar_len = int(s.critic_score * 3)
                bar = '=' * bar_len
                flag = " R" if s.retaken else "  "
                print(f"    {s.index}. [{s.critic_score:4.1f}] {bar:30s}{flag}")

        print(f"\n  Shots ({len(prod.script.shots)}):")
        for s in prod.script.shots:
            flag = " [retaken]" if s.retaken else ""
            score = f" {s.critic_score:.1f}/10" if s.critic_score is not None else "  ---"
            imp_bar = '*' * int(s.importance * 5)
            print(f"    {s.index}. {score} imp={imp_bar:5s}{flag}  {s.description[:50]}")

    # Read manifest for efficiency analysis
    manifest_path = Path(args.out) / "manifest.json"
    if manifest_path.exists():
        import json as _json
        manifest = _json.loads(manifest_path.read_text())
        eff = manifest.get("report_card", {}).get("efficiency", {})
        if eff.get("tokens_saved_by_routing", 0) > 0:
            print("\n  Routing efficiency:")
            print(f"    Actual tokens    : {eff['actual_tokens']:,}")
            print(f"    Naive estimate   : {eff['naive_estimate_tokens']:,}")
            print(f"    Saved by routing : {eff['tokens_saved_by_routing']:,}  "
                  f"({eff['routing_savings_pct']:.0f}%)")

    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
