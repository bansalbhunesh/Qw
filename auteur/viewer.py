"""Web viewer — streams a production in real time via SSE for the demo video.

Launch with: `python -m auteur.viewer`
Open http://localhost:8080 in a browser, submit a premise, and watch the showrunner work.
The SSE stream shows each phase (writing, art direction, rendering, critique, assembly) as it
happens — this is what the 3-minute demo video captures.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .agents.showrunner import Showrunner
from .config import ProductionConfig
from .events import bus


def build_viewer_app() -> FastAPI:
    app = FastAPI(title="Auteur — Live Production Viewer")

    class ProduceReq(BaseModel):
        premise: str
        shots: int = 6

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _VIEWER_HTML

    @app.post("/api/produce")
    def produce(req: ProduceReq):
        prod_id = uuid.uuid4().hex[:12]
        workdir = Path("productions") / prod_id

        def _run():
            cfg = ProductionConfig(shots=req.shots)
            show = Showrunner(cfg, workdir=workdir)
            try:
                show.run(req.premise)
            finally:
                bus.close()

        threading.Thread(target=_run, daemon=True).start()
        return {"id": prod_id}

    @app.get("/api/events")
    def events():
        q = bus.subscribe()

        def generate():
            while True:
                ev = q.get()
                if ev is None:
                    yield "data: {\"kind\": \"done\"}\n\n"
                    break
                yield ev.to_sse()
            bus.unsubscribe(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/productions/{prod_id}/final.mp4")
    def get_final(prod_id: str):
        path = Path("productions") / prod_id / "final.mp4"
        if not path.exists():
            from fastapi import HTTPException
            raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4")

    @app.get("/productions/{prod_id}/manifest.json")
    def get_manifest(prod_id: str):
        path = Path("productions") / prod_id / "manifest.json"
        if not path.exists():
            from fastapi import HTTPException
            raise HTTPException(404)
        return json.loads(path.read_text())

    return app


_VIEWER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auteur — Live Production</title>
<style>
  :root { --bg: #0a0a0f; --card: #14141f; --border: #2a2a3a; --accent: #6366f1;
          --accent2: #f59e0b; --text: #e2e2ef; --dim: #8888a0; --green: #22c55e; --red: #ef4444; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'SF Mono', 'Fira Code', monospace; background: var(--bg); color: var(--text);
         min-height: 100vh; }
  .container { max-width: 900px; margin: 0 auto; padding: 2rem 1rem; }
  h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem; }
  h1 span { color: var(--accent); }
  .subtitle { color: var(--dim); margin-bottom: 2rem; font-size: 0.85rem; }
  .input-row { display: flex; gap: 0.5rem; margin-bottom: 2rem; }
  .input-row input { flex: 1; padding: 0.75rem 1rem; background: var(--card); border: 1px solid var(--border);
                     border-radius: 8px; color: var(--text); font-size: 0.95rem; font-family: inherit; }
  .input-row input:focus { outline: none; border-color: var(--accent); }
  .input-row button { padding: 0.75rem 1.5rem; background: var(--accent); color: white; border: none;
                      border-radius: 8px; font-weight: 600; cursor: pointer; font-family: inherit;
                      font-size: 0.95rem; white-space: nowrap; }
  .input-row button:disabled { opacity: 0.5; cursor: not-allowed; }
  .input-row button:hover:not(:disabled) { filter: brightness(1.15); }
  #timeline { display: flex; flex-direction: column; gap: 1rem; }
  .event { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
           padding: 1rem 1.25rem; animation: slideIn 0.3s ease; }
  .event.phase { border-left: 3px solid var(--accent); }
  .event.shot { border-left: 3px solid var(--accent2); }
  .event.critic { border-left: 3px solid #8b5cf6; }
  .event.retake { border-left: 3px solid var(--red); background: rgba(239,68,68,0.05); }
  .event.budget { border-left: 3px solid #06b6d4; }
  .event.done { border-left: 3px solid var(--green); }
  .event.error { border-left: 3px solid var(--red); }
  .event-header { display: flex; justify-content: space-between; align-items: center;
                  margin-bottom: 0.4rem; }
  .event-kind { font-weight: 600; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .event-stage { color: var(--dim); font-size: 0.75rem; }
  .event-body { color: var(--dim); font-size: 0.85rem; line-height: 1.5; }
  .event-body strong { color: var(--text); }
  .score { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600;
           font-size: 0.8rem; }
  .score.pass { background: rgba(34,197,94,0.15); color: var(--green); }
  .score.fail { background: rgba(239,68,68,0.15); color: var(--red); }
  .budget-bar { margin-top: 0.5rem; }
  .budget-bar .track { background: var(--border); border-radius: 4px; height: 6px; overflow: hidden; }
  .budget-bar .fill { height: 100%; background: var(--accent); border-radius: 4px;
                      transition: width 0.5s ease; }
  .budget-bar .label { font-size: 0.7rem; color: var(--dim); margin-top: 0.2rem;
                       display: flex; justify-content: space-between; }
  .beat-tag { display: inline-block; background: rgba(99,102,241,0.15); color: var(--accent);
              padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.75rem; font-weight: 600;
              margin-right: 0.3rem; }
  .axis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem; margin-top: 0.4rem; }
  .axis-row { display: flex; align-items: center; gap: 0.4rem; }
  .axis-label { font-size: 0.7rem; color: var(--dim); width: 5.5rem; text-align: right; }
  .axis-track { flex: 1; background: var(--border); border-radius: 3px; height: 4px; overflow: hidden; }
  .axis-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
  .axis-val { font-size: 0.7rem; font-weight: 600; width: 2rem; }
  .fix-note { font-size: 0.75rem; color: var(--red); margin-top: 0.3rem; font-style: italic; }
  .dim { color: var(--dim); }
  .summary-card { padding: 0.5rem 0; }
  .summary-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.6rem; color: var(--green); }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                  gap: 0.5rem; margin-bottom: 0.6rem; }
  .summary-stat { text-align: center; }
  .stat-value { display: block; font-size: 1.3rem; font-weight: 700; color: var(--text); }
  .stat-label { font-size: 0.7rem; color: var(--dim); }
  #video-wrap { margin-top: 2rem; text-align: center; display: none; }
  #video-wrap video { max-width: 360px; border-radius: 12px; border: 2px solid var(--accent); }
  @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
</style>
</head>
<body>
<div class="container">
  <h1><span>Auteur</span> — Live Production</h1>
  <p class="subtitle">The budget-aware AI showrunner. Track 2: AI Showrunner.</p>
  <div class="input-row">
    <input id="premise" placeholder="Enter a premise..." value="A lighthouse keeper teaches the drone sent to replace him">
    <button id="go" onclick="start()">Produce</button>
  </div>
  <div id="timeline"></div>
  <div id="video-wrap"><video id="final-video" controls></video></div>
</div>
<script>
let evtSource = null;
function start() {
  const premise = document.getElementById('premise').value.trim();
  if (!premise) return;
  document.getElementById('go').disabled = true;
  document.getElementById('timeline').innerHTML = '';
  document.getElementById('video-wrap').style.display = 'none';
  fetch('/api/produce', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({premise})})
    .then(r => r.json()).then(d => {
      window._prodId = d.id;
      listenEvents();
    });
}
function listenEvents() {
  evtSource = new EventSource('/api/events');
  evtSource.onmessage = e => {
    const ev = JSON.parse(e.data);
    if (ev.kind === 'done') { evtSource.close(); document.getElementById('go').disabled = false; return; }
    addEvent(ev);
  };
}
function addEvent(ev) {
  const tl = document.getElementById('timeline');
  const div = document.createElement('div');
  let cls = 'event';
  if (['script_complete','style_bible_complete','assembly_start','score_complete'].includes(ev.kind)) cls += ' phase';
  else if (ev.kind === 'shot_complete') cls += ' shot';
  else if (ev.kind === 'critic_verdict') cls += ' critic';
  else if (ev.kind === 'retake_decision') cls += ' retake';
  else if (ev.kind === 'budget_update') cls += ' budget';
  else if (ev.kind === 'production_complete') cls += ' done';
  else if (ev.kind === 'production_failed') cls += ' error';
  div.className = cls;
  div.innerHTML = renderEvent(ev);
  tl.appendChild(div);
  div.scrollIntoView({behavior:'smooth', block:'end'});
  if (ev.kind === 'production_complete' && window._prodId) {
    const wrap = document.getElementById('video-wrap');
    const vid = document.getElementById('final-video');
    vid.src = '/productions/' + window._prodId + '/final.mp4';
    wrap.style.display = 'block';
  }
}
function renderEvent(ev) {
  const hdr = `<div class="event-header"><span class="event-kind">${ev.kind.replace(/_/g,' ')}</span><span class="event-stage">${ev.stage}</span></div>`;
  let body = '';
  if (ev.kind === 'production_start') {
    body = `<strong>Premise:</strong> ${ev.premise || ''}`;
  } else if (ev.kind === 'script_complete') {
    body = `<strong>${ev.logline || ''}</strong><br>${(ev.beats||[]).map(b=>'<span class="beat-tag">'+b.label+'</span> '+b.summary.slice(0,60)).join('<br>')}`;
  } else if (ev.kind === 'style_bible_complete') {
    body = `<strong>Look:</strong> ${(ev.look||'').slice(0,120)}<br><strong>Characters:</strong> ${(ev.characters||[]).map(c=>c.name+' <span class="dim">('+c.description.slice(0,40)+'...)</span>').join(', ')}`;
  } else if (ev.kind === 'critic_verdict') {
    const sc = (ev.overall||0).toFixed(1);
    const cls = ev.overall >= 7 ? 'pass' : 'fail';
    body = `Shot ${ev.index} <span class="score ${cls}">${sc}/10</span>`;
    body += `<div class="axis-grid">`;
    body += axisBar('Prompt', ev.prompt_adherence);
    body += axisBar('Character', ev.character_consistency);
    body += axisBar('Quality', ev.shot_quality);
    body += axisBar('Continuity', ev.visual_continuity);
    body += `</div>`;
    if (ev.fix) body += `<div class="fix-note">Fix: ${ev.fix}</div>`;
  } else if (ev.kind === 'retake_decision') {
    body = `<strong>Retaking shot ${ev.index}</strong> (score=${(ev.score||0).toFixed(1)}, importance=${(ev.importance||0).toFixed(1)})<br><span class="fix-note">${ev.fix||''}</span>`;
  } else if (ev.kind === 'shot_complete') {
    const sc = (ev.score||0).toFixed(1);
    const cls = ev.score >= 7 ? 'pass' : 'fail';
    body = `Shot ${ev.index} <span class="score ${cls}">${sc}/10</span> importance=${(ev.importance||0).toFixed(1)}${ev.retaken ? ' <strong>[RETAKEN]</strong>' : ''}`;
  } else if (ev.kind === 'budget_update') {
    body = `<strong>Budget checkpoint</strong>`;
    body += budgetBar('Tokens', ev.tokens_used, ev.token_budget);
    body += budgetBar('Clips', ev.clips_used, ev.clip_budget);
    body += budgetBar('Retakes', ev.retakes_used, ev.retake_budget);
    if (ev.estimated_cost_usd > 0) body += `<div class="dim" style="margin-top:0.3rem">Est. spend: $${ev.estimated_cost_usd.toFixed(2)} / $${ev.max_spend_usd.toFixed(2)}</div>`;
  } else if (ev.kind === 'score_complete') {
    body = `<strong>Score composed:</strong> mood=${ev.mood}, intensity=${(ev.intensity||0).toFixed(1)}`;
  } else if (ev.kind === 'parallel_render_start') {
    body = `<strong>Parallel render:</strong> ${ev.n_shots} shots with ${ev.workers} workers (no-consistency mode)`;
  } else if (ev.kind === 'quality_gate') {
    body = `<strong>Quality gate:</strong> kept ${ev.kept} clips, dropped ${ev.dropped} scoring below ${(ev.threshold||0).toFixed(1)}`;
  } else if (ev.kind === 'production_complete') {
    const b = ev.budget || {};
    const pct = b.token_budget ? (b.tokens_used/b.token_budget*100).toFixed(1) : '0';
    body = `<div class="summary-card">`;
    body += `<div class="summary-title">Production Wrapped</div>`;
    body += `<div class="summary-grid">`;
    body += `<div class="summary-stat"><span class="stat-value">${b.tokens_used||0}</span><span class="stat-label">tokens (${pct}% of budget)</span></div>`;
    body += `<div class="summary-stat"><span class="stat-value">${b.clips_used||0}</span><span class="stat-label">clips rendered</span></div>`;
    body += `<div class="summary-stat"><span class="stat-value">${b.retakes_used||0}</span><span class="stat-label">retakes</span></div>`;
    if (b.estimated_cost_usd > 0) body += `<div class="summary-stat"><span class="stat-value">$${b.estimated_cost_usd.toFixed(2)}</span><span class="stat-label">spent</span></div>`;
    body += `</div>`;
    body += budgetBar('Tokens', b.tokens_used, b.token_budget);
    body += budgetBar('Clips', b.clips_used, b.clip_budget);
    body += `</div>`;
  } else {
    body = JSON.stringify(ev).slice(0,200);
  }
  return hdr + `<div class="event-body">${body}</div>`;
}
function axisBar(label, val) {
  val = val || 0;
  const pct = Math.min(100, val * 10);
  const color = val >= 7 ? 'var(--green)' : val >= 5 ? 'var(--accent2)' : 'var(--red)';
  return `<div class="axis-row"><span class="axis-label">${label}</span><div class="axis-track"><div class="axis-fill" style="width:${pct}%;background:${color}"></div></div><span class="axis-val">${val.toFixed(1)}</span></div>`;
}
function budgetBar(label, used, total) {
  const pct = total ? Math.min(100, used/total*100) : 0;
  return `<div class="budget-bar"><div class="track"><div class="fill" style="width:${pct}%"></div></div><div class="label"><span>${label}</span><span>${used}/${total}</span></div></div>`;
}
</script>
</body>
</html>
"""


def serve_viewer() -> None:
    import uvicorn
    from . import log as _logmod
    _logmod.setup()
    port = int(os.getenv("VIEWER_PORT", "8080"))
    print(f"Auteur viewer at http://localhost:{port}")
    uvicorn.run(build_viewer_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    serve_viewer()
