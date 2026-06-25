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
  if (['script_complete','style_bible_complete','assembly_start'].includes(ev.kind)) cls += ' phase';
  else if (ev.kind === 'shot_complete') cls += ' shot';
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
  if (ev.kind === 'script_complete') {
    body = `<strong>${ev.logline || ''}</strong><br>${(ev.beats||[]).map(b=>b.label+': '+b.summary.slice(0,60)).join('<br>')}`;
  } else if (ev.kind === 'style_bible_complete') {
    body = `<strong>Look:</strong> ${(ev.look||'').slice(0,120)}<br><strong>Characters:</strong> ${(ev.characters||[]).map(c=>c.name).join(', ')}`;
  } else if (ev.kind === 'shot_complete') {
    const sc = (ev.score||0).toFixed(1);
    const cls = ev.score >= 7 ? 'pass' : 'fail';
    body = `Shot ${ev.index} <span class="score ${cls}">${sc}/10</span> importance=${(ev.importance||0).toFixed(1)}${ev.retaken ? ' <strong>[RETAKEN]</strong>' : ''}`;
  } else if (ev.kind === 'production_complete') {
    const b = ev.budget || {};
    body = `<strong>Done!</strong> ${b.tokens_used||0} tokens, ${b.clips_used||0} clips, ${b.retakes_used||0} retakes`;
    body += budgetBar('Tokens', b.tokens_used, b.token_budget);
    body += budgetBar('Clips', b.clips_used, b.clip_budget);
  } else {
    body = JSON.stringify(ev).slice(0,200);
  }
  return hdr + `<div class="event-body">${body}</div>`;
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
