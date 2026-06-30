"""Multi-episode orchestrator — runs a serialized micro-drama series.

Usage:
    python -m auteur.series "A detective learns her informant has been her husband all along" --episodes 3

Architecture
────────────
Series Mode extends Auteur from single-episode productions to multi-episode arcs while
maintaining visual consistency and narrative continuity across the full run.

Key design decisions:

  1. **Style Bible Locking** — Episode 1 runs the full Showrunner pipeline and generates
     the canonical Style Bible (characters, look, color palette). This Bible is extracted
     from Episode 1's manifest and *injected* into every subsequent episode's Art Director
     cache, so character appearances never drift across episodes.

  2. **Continuation Premise Generation** — After each episode completes, the series
     orchestrator feeds the episode's logline and final beat to Qwen (creative tier) to
     generate a natural one-line continuation premise for the next episode. This creates
     a "Previously on…" hand-off that maintains narrative momentum.

  3. **Per-Episode Budget Isolation** — Each episode gets its own Showrunner instance
     with a fresh BudgetGovernor, so a single episode's budget overrun never starves
     later episodes. The series manifest aggregates totals across all episodes.

  4. **Graceful Degradation** — Individual episode failures are caught and logged but do
     not halt the series. The series ships whatever episodes it successfully produced.

Outputs
───────
  series_out/
    episode_1/  final.mp4 · storyboard.html · manifest.json · ledger.json
    episode_2/  …
    episode_N/  …
    series_manifest.json   ← combined series metadata (all episodes + aggregate budget)
    series_storyboard.html ← combined storyboard across all episodes
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from . import log as _logmod
from .config import ProductionConfig

_log = _logmod.get("series")

_CONTINUATION_SYS = """\
You are a TV series writer. Given the logline and final beat of a just-completed episode,
write a compelling ONE-LINE premise for the NEXT episode that continues the story naturally.
The characters and setting carry over — only the dramatic situation advances.
Return ONLY the one-line premise string, nothing else."""

_CONTINUATION_USER = """\
Series title premise: {series_premise}
Episode {ep_num} logline: {logline}
Episode {ep_num} final beat: {final_beat}
Write the Episode {next_ep} premise:"""


def _generate_continuation(client, ep_num: int, series_premise: str,
                            logline: str, final_beat: str) -> str:
    """Ask Qwen to write a continuation premise from the last episode's final beat."""
    from .config import Tier
    try:
        msg = client.chat(
            "series_writer",
            Tier.CREATIVE,
            [
                {"role": "system", "content": _CONTINUATION_SYS},
                {"role": "user", "content": _CONTINUATION_USER.format(
                    series_premise=series_premise,
                    ep_num=ep_num,
                    logline=logline,
                    final_beat=final_beat,
                    next_ep=ep_num + 1,
                )},
            ],
            temperature=0.8,
        )
        # chat() returns the assistant message string
        return str(msg).strip().strip('"').strip("'")
    except Exception:
        _log.warning("continuation premise generation failed — using generic continuation")
        return f"Continuing from where we left off: {series_premise} — what happens next?"


def _load_series_bible(manifest_path: Path) -> dict:
    """Extract the Style Bible (characters + look) from a completed episode's manifest."""
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text())
        return manifest.get("style", {})
    except Exception:
        return {}


def _inject_bible(showrunner, bible: dict) -> None:
    """Pre-populate the Art Director's cached style so Episode N re-uses Episode 1's Bible."""
    if not bible:
        return
    try:
        from .agents.art_director import ArtDirector
        from .models import StyleBible, Character

        characters = [
            Character(name=c["name"], description=c["description"],
                      voice=c.get("voice", ""))
            for c in bible.get("characters", [])
        ]
        style = StyleBible(
            look=bible.get("look", ""),
            characters=characters,
        )
        showrunner.art._cached_bible = style
        _log.info("series bible injected: %d characters, look='%s...'",
                  len(characters), style.look[:60])
    except Exception:
        _log.warning("bible injection failed — Episode N will re-derive it:\n%s",
                     traceback.format_exc())


def _write_series_manifest(episodes: list[dict], outdir: Path,
                           series_premise: str) -> None:
    """Write a combined series_manifest.json aggregating all episode data."""
    total_tokens = sum(e.get("budget", {}).get("tokens_used", 0) for e in episodes)
    total_clips = sum(e.get("budget", {}).get("clips_used", 0) for e in episodes)
    total_cost = sum(e.get("budget", {}).get("estimated_cost_usd", 0.0) for e in episodes)
    scores = [e.get("report_card", {}).get("avg_critic_score", 0.0) for e in episodes
              if e.get("report_card", {}).get("avg_critic_score")]

    manifest = {
        "series_premise": series_premise,
        "episodes": len(episodes),
        "episode_manifests": [e.get("_path", "") for e in episodes],
        "aggregate": {
            "total_tokens": total_tokens,
            "total_clips": total_clips,
            "total_estimated_cost_usd": round(total_cost, 4),
            "avg_critic_score": round(sum(scores) / len(scores), 2) if scores else None,
            "per_episode": [
                {
                    "episode": i + 1,
                    "premise": e.get("premise", ""),
                    "logline": e.get("logline", ""),
                    "final": e.get("final", ""),
                    "avg_score": e.get("report_card", {}).get("avg_critic_score"),
                    "tokens": e.get("budget", {}).get("tokens_used", 0),
                    "clips": e.get("budget", {}).get("clips_used", 0),
                }
                for i, e in enumerate(episodes)
            ],
        },
    }
    path = outdir / "series_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    _log.info("series manifest → %s", path)


def _write_series_storyboard(episodes: list[dict], outdir: Path,
                              series_premise: str) -> None:
    """Write a combined HTML storyboard linking all episodes."""
    episode_cards = ""
    for i, ep in enumerate(episodes):
        ep_num = i + 1
        score = ep.get("report_card", {}).get("avg_critic_score", "—")
        tokens = ep.get("budget", {}).get("tokens_used", 0)
        logline = ep.get("logline", "")
        final = ep.get("final", "")
        sb_path = Path(ep.get("_path", "")).parent / "storyboard.html"
        episode_cards += f"""
        <div class="episode-card">
          <div class="ep-badge">Episode {ep_num}</div>
          <div class="ep-logline">{logline}</div>
          <div class="ep-meta">
            <span class="score">⭐ {score}/10</span>
            <span class="tokens">🪙 {tokens:,} tokens</span>
          </div>
          <div class="ep-links">
            {"<a href='file://" + str(final) + "' target='_blank'>▶ Watch</a>" if final else ""}
            {"<a href='file://" + str(sb_path) + "' target='_blank'>📋 Storyboard</a>" if sb_path.exists() else ""}
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Auteur Series — {series_premise[:60]}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d0d14; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
         min-height: 100vh; padding: 2rem; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #a78bfa; margin-bottom: 0.4rem; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; }}
  .episodes {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.2rem; }}
  .episode-card {{ background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px;
                   padding: 1.4rem; transition: border-color 0.2s; }}
  .episode-card:hover {{ border-color: #7c3aed; }}
  .ep-badge {{ display: inline-block; background: #7c3aed22; color: #a78bfa;
               font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
               text-transform: uppercase; padding: 0.2rem 0.7rem; border-radius: 999px;
               border: 1px solid #7c3aed44; margin-bottom: 0.8rem; }}
  .ep-logline {{ font-size: 0.95rem; color: #cbd5e1; line-height: 1.5; margin-bottom: 1rem; }}
  .ep-meta {{ display: flex; gap: 1rem; font-size: 0.82rem; color: #64748b; margin-bottom: 0.8rem; }}
  .score {{ color: #fbbf24; }}
  .ep-links {{ display: flex; gap: 0.8rem; }}
  .ep-links a {{ color: #7c3aed; text-decoration: none; font-size: 0.85rem; font-weight: 600;
                 padding: 0.3rem 0.8rem; border: 1px solid #7c3aed44; border-radius: 6px;
                 transition: background 0.15s; }}
  .ep-links a:hover {{ background: #7c3aed22; }}
</style>
</head>
<body>
<h1>🎬 Auteur Series</h1>
<p class="subtitle">{series_premise}</p>
<div class="episodes">{episode_cards}</div>
</body>
</html>"""
    path = outdir / "series_storyboard.html"
    path.write_text(html, encoding="utf-8")
    _log.info("series storyboard → %s", path)


def run_series(series_premise: str, n_episodes: int, cfg: ProductionConfig,
               outdir: Path, resume: bool = False) -> list[dict]:
    """Run a full N-episode series. Returns list of episode manifests."""
    from .agents.showrunner import Showrunner

    outdir.mkdir(parents=True, exist_ok=True)
    episode_manifests: list[dict] = []
    series_bible: dict = {}
    current_premise = series_premise

    for ep_num in range(1, n_episodes + 1):
        ep_dir = outdir / f"episode_{ep_num}"
        manifest_path = ep_dir / "manifest.json"
        
        # Check if episode is already complete when resuming
        if resume and manifest_path.exists():
            try:
                ep_manifest = json.loads(manifest_path.read_text())
                if ep_manifest.get("final"):
                    _log.info("SERIES: Episode %d already complete, skipping", ep_num)
                    ep_manifest["_path"] = str(manifest_path)
                    episode_manifests.append(ep_manifest)
                    if ep_num == 1:
                        series_bible = _load_series_bible(manifest_path)
                    
                    if ep_num < n_episodes:
                        logline = ep_manifest.get("logline", current_premise)
                        beats = ep_manifest.get("beats", [])
                        final_beat = beats[-1].get("summary", "") if beats else ""
                        from .llm import QwenClient
                        from .budget import BudgetGovernor
                        temp_client = QwenClient(BudgetGovernor(cfg.budget))
                        current_premise = _generate_continuation(
                            temp_client, ep_num, series_premise, logline, final_beat,
                        )
                    continue
            except Exception:
                pass

        _log.info("=" * 60)
        _log.info("SERIES: Starting Episode %d/%d", ep_num, n_episodes)
        _log.info("Premise: %s", current_premise)
        _log.info("=" * 60)

        show = Showrunner(cfg, workdir=ep_dir)

        # Re-inject the Series Bible from Episode 1 into every subsequent episode
        if ep_num > 1 and series_bible:
            _inject_bible(show, series_bible)

        try:
            prod = show.run(current_premise, resume=resume)
        except Exception:
            _log.error("Episode %d failed:\n%s", ep_num, traceback.format_exc())
            episode_manifests.append({"episode": ep_num, "premise": current_premise,
                                      "_path": str(ep_dir / "manifest.json"), "error": True})
            continue

        # Load manifest for aggregation
        manifest_path = ep_dir / "manifest.json"
        try:
            ep_manifest = json.loads(manifest_path.read_text())
        except Exception:
            ep_manifest = {"premise": current_premise}
        ep_manifest["_path"] = str(manifest_path)
        episode_manifests.append(ep_manifest)

        # Lock in the Series Bible after Episode 1
        if ep_num == 1:
            series_bible = _load_series_bible(manifest_path)
            _log.info("Series Bible locked from Episode 1: %d characters",
                      len(series_bible.get("characters", [])))

        # Generate continuation premise for the next episode
        if ep_num < n_episodes:
            logline = ep_manifest.get("logline", current_premise)
            beats = ep_manifest.get("beats", [])
            final_beat = beats[-1].get("summary", "") if beats else ""
            show_client = show.client
            current_premise = _generate_continuation(
                show_client, ep_num, series_premise, logline, final_beat,
            )
            _log.info("Episode %d continuation premise: %s", ep_num + 1, current_premise)

        # Print per-episode summary
        summary = show.governor.summary()
        pct = summary["tokens_used"] / max(1, summary["token_budget"]) * 100
        print(f"\n  Episode {ep_num} complete")
        print(f"    Final cut  : {prod.final_path if prod else 'None'}")
        print(f"    Tokens     : {summary['tokens_used']:,} ({pct:.1f}% of budget)")
        if summary.get("estimated_cost_usd", 0) > 0:
            print(f"    Spend      : ${summary['estimated_cost_usd']:.2f}")
        scored = [s for s in (prod.script.shots if prod and prod.script else [])
                  if s.critic_score is not None]
        if scored:
            avg = sum(s.critic_score for s in scored) / len(scored)
            print(f"    Avg score  : {avg:.1f}/10")

    return episode_manifests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auteur Series — run a multi-episode vertical drama series",
        epilog="Example:\n  python -m auteur.series 'A detective learns her informant is her husband' --episodes 3",
    )
    parser.add_argument("premise", help="one-line series premise (carries across episodes)")
    parser.add_argument("--episodes", type=int, default=3, metavar="N",
                        help="number of episodes to produce (default: 3)")
    parser.add_argument("--shots", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=120_000)
    parser.add_argument("--max-clips", type=int, default=8)
    parser.add_argument("--max-retakes", type=int, default=4)
    parser.add_argument("--max-spend-usd", type=float, default=2.00)
    parser.add_argument("--resolution", default="720P", choices=["480P", "720P", "1080P"])
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"])
    parser.add_argument("--out", default="series_out", help="output directory for the series")
    parser.add_argument("--no-consistency", action="store_true")
    parser.add_argument("--quality-gate", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true", help="resume from last checkpoint if crashed")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    import logging
    _logmod.setup(logging.DEBUG if args.verbose else logging.INFO)

    cfg = ProductionConfig(
        shots=args.shots, resolution=args.resolution, aspect_ratio=args.aspect_ratio,
        consistency=not args.no_consistency, quality_gate=args.quality_gate,
    )
    cfg.budget.max_tokens = args.max_tokens
    cfg.budget.max_clips = args.max_clips
    cfg.budget.max_retakes = args.max_retakes
    cfg.budget.max_spend_usd = args.max_spend_usd

    outdir = Path(args.out)

    print(f"\n{'=' * 60}")
    print(f"  AUTEUR SERIES — {args.episodes} EPISODES")
    print(f"  Premise: {args.premise[:55]}")
    if args.resume:
        print(f"  Mode: RESUME (picking up from vault checkpoints)")
    print(f"{'=' * 60}\n")

    episodes = run_series(args.premise, args.episodes, cfg, outdir, resume=args.resume)

    # Write series-level artifacts
    _write_series_manifest(episodes, outdir, args.premise)
    _write_series_storyboard(episodes, outdir, args.premise)

    # Aggregate summary
    total_tokens = sum(e.get("budget", {}).get("tokens_used", 0) for e in episodes)
    total_cost = sum(e.get("budget", {}).get("estimated_cost_usd", 0.0) for e in episodes)
    scores = [e.get("report_card", {}).get("avg_critic_score") for e in episodes
              if e.get("report_card", {}).get("avg_critic_score")]

    print(f"\n{'=' * 60}")
    print(f"  SERIES COMPLETE — {len(episodes)} episodes")
    print(f"  Series storyboard : {outdir / 'series_storyboard.html'}")
    print(f"  Series manifest   : {outdir / 'series_manifest.json'}")
    print(f"\n  Aggregate budget across all episodes:")
    print(f"    Total tokens : {total_tokens:,}")
    if total_cost > 0:
        print(f"    Total spend  : ${total_cost:.2f}")
    if scores:
        print(f"    Avg quality  : {sum(scores)/len(scores):.1f}/10")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
