"""Storyboard HTML export — a visual production breakdown for judges.

Generates a self-contained HTML file showing every shot's frames alongside its script
data, critic scores, retake status, and budget analytics. This is a first-class deliverable
that proves the pipeline works end-to-end.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from . import log, media

_log = log.get("storyboard")


def export_storyboard(workdir: str | Path, manifest: dict, out_path: str | Path | None = None) -> str:
    workdir = Path(workdir)
    out = Path(out_path) if out_path else workdir / "storyboard.html"

    shots_html = []
    for shot in manifest.get("shots", []):
        frames = _get_frames(workdir, shot)
        score = shot.get("critic_score")
        importance = shot.get("importance", 0)
        retaken = shot.get("retaken", False)

        score_color = _score_color(score)
        imp_bar = _bar(importance, "#6ea8fe")
        score_bar = _bar((score or 0) / 10.0, score_color)

        frames_html = ""
        for uri in frames:
            frames_html += f'<img src="{uri}" class="frame">'
        if not frames_html:
            frames_html = '<div class="no-frames">No frames extracted</div>'

        beat_idx = shot.get("beat", 0)
        beats = manifest.get("beats", [])
        beat_label = beats[beat_idx]["label"] if beat_idx < len(beats) else "?"
        beat_tone = beats[beat_idx].get("tone", "") if beat_idx < len(beats) else ""

        retake_badge = '<span class="badge retake">RETAKEN</span>' if retaken else ""
        score_text = f"{score:.1f}" if score is not None else "---"

        shots_html.append(f"""
        <div class="shot {'retaken' if retaken else ''} {'low-score' if score and score < 7 else ''}">
            <div class="shot-header">
                <span class="shot-num">Shot {shot.get('index', '?')}</span>
                <span class="beat-label">{beat_label}</span>
                <span class="beat-tone">{beat_tone}</span>
                {retake_badge}
            </div>
            <div class="frames-row">{frames_html}</div>
            <div class="shot-meta">
                <div class="meta-row">
                    <label>Description</label>
                    <p>{_esc(shot.get('description', ''))}</p>
                </div>
                <div class="meta-row">
                    <label>Dialogue</label>
                    <p class="dialogue">{_esc(shot.get('dialogue', '')) or '<em>silence</em>'}</p>
                </div>
                <div class="scores-row">
                    <div class="score-item">
                        <span class="score-label">Critic</span>
                        <span class="score-value" style="color:{score_color}">{score_text}</span>
                        <div class="bar-bg"><div class="bar-fill" style="width:{(score or 0)*10}%;background:{score_color}"></div></div>
                    </div>
                    <div class="score-item">
                        <span class="score-label">Importance</span>
                        <span class="score-value">{importance:.2f}</span>
                        <div class="bar-bg"><div class="bar-fill" style="width:{importance*100}%;background:#6ea8fe"></div></div>
                    </div>
                </div>
            </div>
        </div>""")

    budget = manifest.get("budget", {})
    report = manifest.get("report_card", {})
    style = manifest.get("style", {})
    decisions = manifest.get("decisions", [])
    timeline = manifest.get("timeline", [])
    efficiency = report.get("efficiency", {})

    chars_html = ""
    for c in style.get("characters", []):
        chars_html += f"""
        <div class="character">
            <strong>{_esc(c.get('name', ''))}</strong>
            <span class="voice-tag">{_esc(c.get('voice', ''))}</span>
            <p>{_esc(c.get('description', '')[:120])}</p>
        </div>"""

    decisions_html = ""
    for d in decisions:
        icon = "&#x21bb;" if d.get("retake") else "&#x2713;"
        cls = "retake" if d.get("retake") else "pass"
        decisions_html += f"""
        <div class="decision {cls}">
            <span class="dec-icon">{icon}</span>
            Shot {d.get('shot', '?')} &mdash; {_esc(d.get('reason', '')[:100])}
        </div>"""

    timeline_html = ""
    for t in timeline:
        timeline_html += f"""
        <div class="tl-entry">
            <span class="tl-phase">{_esc(t.get('phase', ''))}</span>
            <span class="tl-time">{t.get('elapsed_s', 0):.1f}s</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auteur Storyboard &mdash; {_esc(manifest.get('premise', '')[:60])}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;
  padding:2rem;line-height:1.5}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:1.6rem;color:#fff;margin-bottom:0.3rem}}
.logline{{color:#a0a0b0;font-style:italic;margin-bottom:2rem;font-size:1rem}}
.section{{margin-bottom:2rem}}
.section-title{{font-size:1.1rem;color:#6ea8fe;border-bottom:1px solid #222;
  padding-bottom:0.4rem;margin-bottom:1rem}}
.shot{{background:#13131a;border:1px solid #222;border-radius:12px;margin-bottom:1.5rem;
  overflow:hidden;transition:border-color 0.2s}}
.shot.retaken{{border-color:#a85032}}
.shot.low-score{{border-left:3px solid #a85032}}
.shot-header{{display:flex;align-items:center;gap:0.8rem;padding:0.8rem 1.2rem;
  background:#1a1a24;border-bottom:1px solid #222}}
.shot-num{{font-weight:700;color:#fff;font-size:1rem}}
.beat-label{{background:#6ea8fe20;color:#6ea8fe;padding:0.15rem 0.5rem;border-radius:4px;
  font-size:0.75rem;font-weight:600}}
.beat-tone{{color:#888;font-size:0.75rem}}
.badge{{padding:0.1rem 0.4rem;border-radius:3px;font-size:0.65rem;font-weight:700;
  text-transform:uppercase}}
.badge.retake{{background:#a8503220;color:#e87040}}
.frames-row{{display:flex;gap:0.5rem;padding:1rem;overflow-x:auto;background:#0d0d12}}
.frame{{height:160px;border-radius:6px;object-fit:cover;border:1px solid #333}}
.no-frames{{color:#555;font-size:0.8rem;padding:2rem;text-align:center}}
.shot-meta{{padding:1rem 1.2rem}}
.meta-row{{margin-bottom:0.6rem}}
.meta-row label{{display:block;font-size:0.7rem;color:#666;text-transform:uppercase;
  letter-spacing:0.05em;margin-bottom:0.2rem}}
.meta-row p{{font-size:0.85rem;color:#ccc}}
.dialogue{{font-style:italic;color:#a0a0b0}}
.scores-row{{display:flex;gap:2rem;margin-top:0.8rem}}
.score-item{{flex:1}}
.score-label{{font-size:0.65rem;color:#666;text-transform:uppercase}}
.score-value{{font-size:1.2rem;font-weight:700;margin-left:0.5rem}}
.bar-bg{{height:4px;background:#222;border-radius:2px;margin-top:0.3rem}}
.bar-fill{{height:4px;border-radius:2px;transition:width 0.4s}}
.sidebar-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
.info-card{{background:#13131a;border:1px solid #222;border-radius:10px;padding:1rem}}
.info-card h3{{font-size:0.85rem;color:#6ea8fe;margin-bottom:0.6rem}}
.stat{{display:flex;justify-content:space-between;padding:0.25rem 0;font-size:0.8rem}}
.stat-val{{color:#fff;font-weight:600}}
.character{{background:#1a1a24;border-radius:6px;padding:0.6rem;margin-bottom:0.5rem}}
.character strong{{color:#fff;font-size:0.85rem}}
.character p{{font-size:0.75rem;color:#999;margin-top:0.2rem}}
.voice-tag{{background:#6ea8fe15;color:#6ea8fe;padding:0.1rem 0.35rem;border-radius:3px;
  font-size:0.6rem;margin-left:0.5rem}}
.decision{{padding:0.3rem 0.6rem;font-size:0.75rem;border-radius:4px;margin-bottom:0.3rem}}
.decision.pass{{background:#2a3a2a;color:#7ec87e}}
.decision.retake{{background:#3a2a2a;color:#e87040}}
.dec-icon{{margin-right:0.3rem}}
.tl-entry{{display:flex;justify-content:space-between;padding:0.2rem 0;font-size:0.75rem}}
.tl-phase{{color:#ccc}}.tl-time{{color:#6ea8fe;font-weight:600}}
.header-meta{{display:flex;gap:2rem;color:#888;font-size:0.8rem;margin-bottom:1.5rem}}
footer{{text-align:center;color:#444;font-size:0.7rem;margin-top:3rem;padding-top:1rem;
  border-top:1px solid #1a1a1a}}
</style></head><body>
<div class="container">
<h1>Auteur &mdash; Production Storyboard</h1>
<p class="logline">&ldquo;{_esc(manifest.get('logline', ''))}&rdquo;</p>
<div class="header-meta">
    <span>Premise: {_esc(manifest.get('premise', '')[:80])}</span>
    <span>Shots: {report.get('shots_rendered', 0)}/{report.get('shots_planned', 0)}</span>
    <span>Avg Score: {report.get('avg_critic_score', 0):.1f}/10</span>
    <span>Budget: {budget.get('tokens_used', 0):,}/{budget.get('token_budget', 0):,} tokens</span>
</div>

<div class="sidebar-grid">
    <div class="info-card">
        <h3>Budget Summary</h3>
        <div class="stat"><span>Tokens</span><span class="stat-val">{budget.get('tokens_used',0):,} / {budget.get('token_budget',0):,}</span></div>
        <div class="stat"><span>Clips</span><span class="stat-val">{budget.get('clips_used',0)} / {budget.get('clip_budget',0)}</span></div>
        <div class="stat"><span>Retakes</span><span class="stat-val">{budget.get('retakes_used',0)} / {budget.get('retake_budget',0)}</span></div>
        <div class="stat"><span>Est. Cost</span><span class="stat-val">${budget.get('estimated_cost_usd',0):.2f}</span></div>
        <div class="stat"><span>Utilization</span><span class="stat-val">{report.get('budget_utilization_pct',0):.1f}%</span></div>
    </div>
    <div class="info-card">
        <h3>Style Bible</h3>
        <p style="font-size:0.75rem;color:#999;margin-bottom:0.5rem">{_esc(style.get('look', '')[:150])}</p>
        {chars_html}
    </div>
    <div class="info-card">
        <h3>Routing Efficiency</h3>
        <div class="stat"><span>Actual tokens</span><span class="stat-val">{efficiency.get('actual_tokens',0):,}</span></div>
        <div class="stat"><span>Naive estimate</span><span class="stat-val">{efficiency.get('naive_estimate_tokens',0):,}</span></div>
        <div class="stat"><span>Saved by routing</span><span class="stat-val">{efficiency.get('tokens_saved_by_routing',0):,} ({efficiency.get('routing_savings_pct',0):.0f}%)</span></div>
    </div>
    <div class="info-card">
        <h3>Timeline</h3>
        {timeline_html if timeline_html else '<p style="color:#555;font-size:0.75rem">No timeline data</p>'}
    </div>
</div>

<div class="section">
    <h2 class="section-title">Shot-by-Shot Breakdown</h2>
    {"".join(shots_html)}
</div>

<div class="section">
    <h2 class="section-title">Governor Decisions</h2>
    {decisions_html if decisions_html else '<p style="color:#555">No decisions recorded</p>'}
</div>

<footer>Generated by Auteur &mdash; The Budget-Aware AI Showrunner</footer>
</div></body></html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    _log.info("storyboard -> %s", out)
    return str(out)


def _get_frames(workdir: Path, shot: dict) -> list[str]:
    clip = shot.get("clip")
    if not clip or not Path(clip).exists():
        return []
    try:
        frame_paths = media.extract_frames(clip, n=3)
        return [media.frame_to_data_uri(f) for f in frame_paths]
    except Exception:
        return []


def _score_color(score: float | None) -> str:
    if score is None:
        return "#666"
    if score >= 8:
        return "#5cb85c"
    if score >= 7:
        return "#6ea8fe"
    if score >= 5:
        return "#f0ad4e"
    return "#d9534f"


def _bar(ratio: float, color: str) -> str:
    pct = max(0, min(100, ratio * 100))
    return f'<div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
