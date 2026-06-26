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
        quality_gate: float = 0.0
        max_spend_usd: float = 2.00

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _VIEWER_HTML

    @app.post("/api/produce")
    def produce(req: ProduceReq):
        prod_id = uuid.uuid4().hex[:12]
        workdir = Path("productions") / prod_id

        def _run():
            cfg = ProductionConfig(
                shots=req.shots,
                quality_gate=req.quality_gate,
            )
            cfg.budget.max_spend_usd = req.max_spend_usd
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

    @app.get("/productions/{prod_id}/ledger.json")
    def get_ledger(prod_id: str):
        path = Path("productions") / prod_id / "ledger.json"
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
<title>Auteur — Production Control Room</title>
<style>
  :root {
    --bg: #08080d; --surface: #0f0f18; --card: #151520; --border: #252535;
    --accent: #6366f1; --accent-dim: rgba(99,102,241,0.15);
    --amber: #f59e0b; --amber-dim: rgba(245,158,11,0.12);
    --green: #22c55e; --green-dim: rgba(34,197,94,0.12);
    --red: #ef4444; --red-dim: rgba(239,68,68,0.08);
    --cyan: #06b6d4; --cyan-dim: rgba(6,182,212,0.12);
    --purple: #8b5cf6; --purple-dim: rgba(139,92,246,0.12);
    --text: #e8e8f0; --dim: #7c7c96; --muted: #55556a;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh;
         overflow-x: hidden; }

  .header { background: var(--surface); border-bottom: 1px solid var(--border);
            padding: 1rem 2rem; display: flex; align-items: center; gap: 1rem; }
  .logo { font-size: 1.4rem; font-weight: 800; letter-spacing: -0.02em; }
  .logo span { color: var(--accent); }
  .header-tag { font-size: 0.7rem; color: var(--dim); background: var(--accent-dim);
                padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600;
                letter-spacing: 0.04em; text-transform: uppercase; }
  .header-spacer { flex: 1; }
  .header-status { font-size: 0.75rem; color: var(--dim); }
  .header-status.active { color: var(--green); }

  .main { display: grid; grid-template-columns: 1fr 320px; min-height: calc(100vh - 56px); }
  @media (max-width: 900px) { .main { grid-template-columns: 1fr; } .sidebar { display: none; } }

  .content { padding: 1.5rem 2rem; overflow-y: auto; max-height: calc(100vh - 56px); }

  .input-section { background: var(--card); border: 1px solid var(--border);
                   border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem; }
  .input-label { font-size: 0.7rem; color: var(--dim); text-transform: uppercase;
                 letter-spacing: 0.06em; font-weight: 600; margin-bottom: 0.5rem; }
  .input-row { display: flex; gap: 0.5rem; }
  .input-row input { flex: 1; padding: 0.65rem 0.9rem; background: var(--surface);
                     border: 1px solid var(--border); border-radius: 8px; color: var(--text);
                     font-size: 0.9rem; font-family: inherit; }
  .input-row input:focus { outline: none; border-color: var(--accent);
                           box-shadow: 0 0 0 3px var(--accent-dim); }
  .btn { padding: 0.65rem 1.25rem; background: var(--accent); color: white; border: none;
         border-radius: 8px; font-weight: 600; cursor: pointer; font-family: inherit;
         font-size: 0.85rem; white-space: nowrap; transition: all 0.15s; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn:hover:not(:disabled) { filter: brightness(1.15); transform: translateY(-1px); }
  .config-row { display: flex; gap: 1rem; margin-top: 0.7rem; }
  .config-field { display: flex; flex-direction: column; gap: 0.2rem; }
  .config-field label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase;
                        letter-spacing: 0.04em; }
  .config-field input, .config-field select { padding: 0.35rem 0.5rem; background: var(--surface);
         border: 1px solid var(--border); border-radius: 5px; color: var(--text);
         font-size: 0.75rem; font-family: inherit; width: 80px; }

  #timeline { display: flex; flex-direction: column; gap: 0.6rem; }

  .ev { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
        padding: 0.85rem 1rem; animation: slideIn 0.25s ease; position: relative;
        overflow: hidden; }
  .ev::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
  .ev.phase::before { background: var(--accent); }
  .ev.shot::before { background: var(--amber); }
  .ev.critic::before { background: var(--purple); }
  .ev.retake::before { background: var(--red); }
  .ev.budget::before { background: var(--cyan); }
  .ev.done::before { background: var(--green); }
  .ev.error::before { background: var(--red); }

  .ev-head { display: flex; justify-content: space-between; align-items: center;
             margin-bottom: 0.3rem; }
  .ev-kind { font-weight: 700; font-size: 0.75rem; text-transform: uppercase;
             letter-spacing: 0.06em; }
  .ev.phase .ev-kind { color: var(--accent); }
  .ev.shot .ev-kind { color: var(--amber); }
  .ev.critic .ev-kind { color: var(--purple); }
  .ev.retake .ev-kind { color: var(--red); }
  .ev.budget .ev-kind { color: var(--cyan); }
  .ev.done .ev-kind { color: var(--green); }
  .ev-stage { color: var(--muted); font-size: 0.65rem; font-weight: 500; }
  .ev-body { color: var(--dim); font-size: 0.8rem; line-height: 1.5; }
  .ev-body strong { color: var(--text); font-weight: 600; }

  .badge { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 4px;
           font-weight: 700; font-size: 0.75rem; }
  .badge.pass { background: var(--green-dim); color: var(--green); }
  .badge.fail { background: var(--red-dim); color: var(--red); }

  .bar-row { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.25rem; }
  .bar-label { font-size: 0.65rem; color: var(--muted); width: 5.5rem; text-align: right;
               flex-shrink: 0; }
  .bar-track { flex: 1; background: var(--border); border-radius: 3px; height: 4px;
               overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
  .bar-val { font-size: 0.65rem; font-weight: 700; width: 2.5rem; flex-shrink: 0; }
  .bar-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.2rem; margin-top: 0.35rem; }

  .tag { display: inline-block; background: var(--accent-dim); color: var(--accent);
         padding: 0.08rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;
         margin-right: 0.25rem; }
  .fix { font-size: 0.7rem; color: var(--red); margin-top: 0.25rem; font-style: italic; }

  .budget-block { margin-top: 0.4rem; }
  .budget-track { background: var(--border); border-radius: 4px; height: 5px;
                  overflow: hidden; margin-top: 0.15rem; }
  .budget-fill { height: 100%; background: var(--accent); border-radius: 4px;
                 transition: width 0.5s ease; }
  .budget-meta { font-size: 0.65rem; color: var(--muted); display: flex;
                 justify-content: space-between; margin-top: 0.15rem; }

  .summary { padding: 0.3rem 0; }
  .summary-title { font-size: 1rem; font-weight: 800; color: var(--green);
                   margin-bottom: 0.6rem; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
               gap: 0.5rem; margin-bottom: 0.7rem; }
  .stat { text-align: center; padding: 0.5rem; background: var(--surface);
          border-radius: 8px; border: 1px solid var(--border); }
  .stat-val { display: block; font-size: 1.2rem; font-weight: 800; color: var(--text); }
  .stat-lbl { font-size: 0.6rem; color: var(--muted); text-transform: uppercase;
              letter-spacing: 0.04em; }

  .sidebar { background: var(--surface); border-left: 1px solid var(--border);
             padding: 1.25rem; overflow-y: auto; max-height: calc(100vh - 56px); }
  .sb-section { margin-bottom: 1.25rem; }
  .sb-title { font-size: 0.65rem; color: var(--muted); text-transform: uppercase;
              letter-spacing: 0.08em; font-weight: 700; margin-bottom: 0.5rem;
              padding-bottom: 0.3rem; border-bottom: 1px solid var(--border); }
  .sb-logline { font-size: 0.8rem; color: var(--text); font-style: italic;
                line-height: 1.4; margin-bottom: 0.5rem; }
  .sb-char { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem; }
  .sb-char-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent);
                 flex-shrink: 0; }
  .sb-char-name { font-size: 0.75rem; font-weight: 600; color: var(--text); }
  .sb-char-desc { font-size: 0.65rem; color: var(--dim); }
  .sb-look { font-size: 0.7rem; color: var(--dim); line-height: 1.4; }
  .sb-shot { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;
             padding: 0.3rem 0.4rem; border-radius: 6px; transition: background 0.2s; }
  .sb-shot.active { background: var(--accent-dim); }
  .sb-shot-idx { width: 20px; height: 20px; border-radius: 50%; display: flex;
                 align-items: center; justify-content: center; font-size: 0.6rem;
                 font-weight: 700; background: var(--border); color: var(--dim);
                 flex-shrink: 0; }
  .sb-shot.scored .sb-shot-idx { background: var(--green-dim); color: var(--green); }
  .sb-shot.failed .sb-shot-idx { background: var(--red-dim); color: var(--red); }
  .sb-shot-info { font-size: 0.65rem; color: var(--dim); flex: 1; }
  .sb-shot-score { font-size: 0.7rem; font-weight: 700; }

  #video-wrap { margin-top: 1.5rem; text-align: center; display: none; }
  #video-wrap video { max-width: 360px; border-radius: 12px;
                      border: 2px solid var(--accent);
                      box-shadow: 0 8px 32px rgba(99,102,241,0.2); }
  #video-label { font-size: 0.7rem; color: var(--dim); margin-top: 0.5rem; }

  @keyframes slideIn { from { opacity: 0; transform: translateY(6px); }
                       to { opacity: 1; transform: none; } }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .pulsing { animation: pulse 1.5s ease infinite; }
</style>
</head>
<body>
<div class="header">
  <div class="logo"><span>Auteur</span></div>
  <div class="header-tag">AI Showrunner</div>
  <div class="header-spacer"></div>
  <div class="header-status" id="status">Ready</div>
</div>
<div class="main">
  <div class="content" id="content">
    <div class="input-section">
      <div class="input-label">Premise</div>
      <div class="input-row">
        <input id="premise" placeholder="A lighthouse keeper teaches the drone sent to replace him..."
               value="A lighthouse keeper teaches the drone sent to replace him">
        <button class="btn" id="go" onclick="start()">Produce</button>
      </div>
      <div class="config-row">
        <div class="config-field"><label>Shots</label><input id="cfg-shots" type="number" value="6" min="2" max="12"></div>
        <div class="config-field"><label>Max spend</label><input id="cfg-spend" type="number" value="2.00" min="0.10" max="20.00" step="0.10"></div>
        <div class="config-field"><label>Quality gate</label><input id="cfg-gate" type="number" value="0" min="0" max="10" step="0.5"></div>
      </div>
    </div>
    <div id="timeline"></div>
    <div id="video-wrap">
      <video id="final-video" controls></video>
      <div id="video-label"></div>
    </div>
  </div>
  <div class="sidebar" id="sidebar">
    <div class="sb-section" id="sb-script" style="display:none">
      <div class="sb-title">Script</div>
      <div class="sb-logline" id="sb-logline"></div>
    </div>
    <div class="sb-section" id="sb-style" style="display:none">
      <div class="sb-title">Style Bible</div>
      <div id="sb-chars"></div>
      <div class="sb-look" id="sb-look"></div>
    </div>
    <div class="sb-section" id="sb-shots" style="display:none">
      <div class="sb-title">Shot Tracker</div>
      <div id="sb-shot-list"></div>
    </div>
    <div class="sb-section" id="sb-budget" style="display:none">
      <div class="sb-title">Budget</div>
      <div id="sb-budget-content"></div>
    </div>
  </div>
</div>
<script>
let evtSource=null, shotCount=0;
const state={shots:{},budget:{}};

function start(){
  const premise=document.getElementById('premise').value.trim();
  if(!premise) return;
  const shots=parseInt(document.getElementById('cfg-shots').value)||6;
  const spend=parseFloat(document.getElementById('cfg-spend').value)||2.0;
  const gate=parseFloat(document.getElementById('cfg-gate').value)||0;
  document.getElementById('go').disabled=true;
  document.getElementById('timeline').innerHTML='';
  document.getElementById('video-wrap').style.display='none';
  document.getElementById('status').textContent='Producing...';
  document.getElementById('status').className='header-status active pulsing';
  ['sb-script','sb-style','sb-shots','sb-budget'].forEach(id=>document.getElementById(id).style.display='none');
  fetch('/api/produce',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({premise,shots,quality_gate:gate,max_spend_usd:spend})})
    .then(r=>r.json()).then(d=>{window._prodId=d.id;listen();});
}

function listen(){
  evtSource=new EventSource('/api/events');
  evtSource.onmessage=e=>{
    const ev=JSON.parse(e.data);
    if(ev.kind==='done'){
      evtSource.close();
      document.getElementById('go').disabled=false;
      document.getElementById('status').textContent='Complete';
      document.getElementById('status').className='header-status active';
      return;
    }
    addEvent(ev);
    updateSidebar(ev);
  };
}

function addEvent(ev){
  const tl=document.getElementById('timeline');
  const d=document.createElement('div');
  let cls='ev';
  if(['script_complete','style_bible_complete','assembly_start','score_complete'].includes(ev.kind)) cls+=' phase';
  else if(ev.kind==='shot_complete') cls+=' shot';
  else if(ev.kind==='critic_verdict') cls+=' critic';
  else if(ev.kind==='retake_decision') cls+=' retake';
  else if(ev.kind==='budget_update') cls+=' budget';
  else if(ev.kind==='production_complete') cls+=' done';
  else if(ev.kind==='production_failed') cls+=' error';
  d.className=cls;
  d.innerHTML=render(ev);
  tl.appendChild(d);
  d.scrollIntoView({behavior:'smooth',block:'end'});
  if(ev.kind==='production_complete'&&window._prodId){
    const w=document.getElementById('video-wrap');
    const v=document.getElementById('final-video');
    v.src='/productions/'+window._prodId+'/final.mp4';
    document.getElementById('video-label').textContent='Production '+window._prodId;
    w.style.display='block';
    w.scrollIntoView({behavior:'smooth'});
  }
}

function updateSidebar(ev){
  if(ev.kind==='script_complete'){
    document.getElementById('sb-script').style.display='';
    document.getElementById('sb-logline').textContent=ev.logline||'';
    shotCount=ev.n_shots||6;
    document.getElementById('sb-shots').style.display='';
    let html='';
    for(let i=0;i<shotCount;i++) html+=`<div class="sb-shot" id="sb-s${i}"><div class="sb-shot-idx">${i}</div><div class="sb-shot-info">Pending</div></div>`;
    document.getElementById('sb-shot-list').innerHTML=html;
  }
  if(ev.kind==='style_bible_complete'){
    document.getElementById('sb-style').style.display='';
    const chars=(ev.characters||[]).map(c=>`<div class="sb-char"><div class="sb-char-dot"></div><div><div class="sb-char-name">${c.name}</div><div class="sb-char-desc">${(c.description||'').slice(0,60)}...</div></div></div>`).join('');
    document.getElementById('sb-chars').innerHTML=chars;
    document.getElementById('sb-look').textContent=(ev.look||'').slice(0,100);
  }
  if(ev.kind==='critic_verdict'){
    const el=document.getElementById('sb-s'+ev.index);
    if(el){
      const pass=ev.overall>=7;
      el.className='sb-shot'+(pass?' scored':' failed');
      el.querySelector('.sb-shot-idx').textContent=ev.overall.toFixed(0);
      el.querySelector('.sb-shot-info').innerHTML=`<span class="sb-shot-score" style="color:${pass?'var(--green)':'var(--red)'}">${ev.overall.toFixed(1)}</span>`;
    }
  }
  if(ev.kind==='shot_complete'){
    const el=document.getElementById('sb-s'+ev.index);
    if(el){
      el.className='sb-shot'+(ev.score>=7?' scored':' failed');
      let info=`<span class="sb-shot-score" style="color:${ev.score>=7?'var(--green)':'var(--red)'}">${ev.score.toFixed(1)}</span>`;
      if(ev.retaken) info+=' <span style="color:var(--red);font-size:0.6rem">RETAKEN</span>';
      el.querySelector('.sb-shot-info').innerHTML=info;
    }
  }
  if(ev.kind==='budget_update'||ev.kind==='production_complete'){
    const b=ev.budget||ev;
    if(b.tokens_used!==undefined){
      document.getElementById('sb-budget').style.display='';
      document.getElementById('sb-budget-content').innerHTML=
        budgetBlock('Tokens',b.tokens_used,b.token_budget)+
        budgetBlock('Clips',b.clips_used,b.clip_budget)+
        budgetBlock('Retakes',b.retakes_used,b.retake_budget)+
        (b.estimated_cost_usd>0?`<div style="font-size:0.7rem;color:var(--dim);margin-top:0.4rem">Spend: $${b.estimated_cost_usd.toFixed(2)} / $${b.max_spend_usd.toFixed(2)}</div>`:'');
    }
  }
}

function render(ev){
  const hdr=`<div class="ev-head"><span class="ev-kind">${ev.kind.replace(/_/g,' ')}</span><span class="ev-stage">${ev.stage}</span></div>`;
  let b='';
  if(ev.kind==='production_start'){
    b=`<strong>Premise:</strong> ${ev.premise||''}`;
  } else if(ev.kind==='script_complete'){
    b=`<strong>${ev.logline||''}</strong><br>${(ev.beats||[]).map(x=>'<span class="tag">'+x.label+'</span> '+x.summary.slice(0,55)).join('<br>')}`;
  } else if(ev.kind==='style_bible_complete'){
    b=`<strong>Look:</strong> ${(ev.look||'').slice(0,100)}<br><strong>Characters:</strong> ${(ev.characters||[]).map(c=>c.name).join(', ')}`;
  } else if(ev.kind==='critic_verdict'){
    const pass=ev.overall>=7;
    b=`Shot ${ev.index} <span class="badge ${pass?'pass':'fail'}">${ev.overall.toFixed(1)}</span>`;
    b+=`<div class="bar-grid">`;
    b+=bar('Prompt',ev.prompt_adherence);
    b+=bar('Character',ev.character_consistency);
    b+=bar('Quality',ev.shot_quality);
    b+=bar('Continuity',ev.visual_continuity);
    b+=`</div>`;
    if(ev.fix) b+=`<div class="fix">Fix: ${ev.fix}</div>`;
  } else if(ev.kind==='retake_decision'){
    b=`<strong>Retaking shot ${ev.index}</strong> (score=${(ev.score||0).toFixed(1)}, importance=${(ev.importance||0).toFixed(1)})<br><span class="fix">${ev.fix||''}</span>`;
  } else if(ev.kind==='shot_complete'){
    const pass=ev.score>=7;
    b=`Shot ${ev.index} <span class="badge ${pass?'pass':'fail'}">${(ev.score||0).toFixed(1)}</span> imp=${(ev.importance||0).toFixed(1)}${ev.retaken?' <strong style="color:var(--red)">[RETAKEN]</strong>':''}`;
  } else if(ev.kind==='budget_update'){
    b=`<strong>Budget checkpoint</strong>`;
    b+=budgetBlock('Tokens',ev.tokens_used,ev.token_budget);
    b+=budgetBlock('Clips',ev.clips_used,ev.clip_budget);
    b+=budgetBlock('Retakes',ev.retakes_used,ev.retake_budget);
    if(ev.estimated_cost_usd>0) b+=`<div style="font-size:0.7rem;color:var(--dim);margin-top:0.3rem">Spend: $${ev.estimated_cost_usd.toFixed(2)} / $${ev.max_spend_usd.toFixed(2)}</div>`;
  } else if(ev.kind==='assembly_start'){
    b=`<strong>Assembling ${ev.n_clips} clips</strong>`;
    if(ev.transitions&&ev.transitions.length) b+=`<br><span style="color:var(--dim);font-size:0.7rem">Transitions: ${ev.transitions.join(' &#8594; ')}</span>`;
  } else if(ev.kind==='score_complete'){
    b=`<strong>Score:</strong> mood=${ev.mood}, intensity=${(ev.intensity||0).toFixed(1)}`;
  } else if(ev.kind==='parallel_render_start'){
    b=`<strong>Parallel render:</strong> ${ev.n_shots} shots, ${ev.workers} workers`;
  } else if(ev.kind==='quality_gate'){
    b=`<strong>Quality gate:</strong> kept ${ev.kept}, dropped ${ev.dropped} below ${(ev.threshold||0).toFixed(1)}`;
  } else if(ev.kind==='production_complete'){
    const bg=ev.budget||{};
    const pct=bg.token_budget?(bg.tokens_used/bg.token_budget*100).toFixed(1):'0';
    const rc=ev.report_card||{};
    b=`<div class="summary"><div class="summary-title">Production Wrapped</div>`;
    b+=`<div class="stat-grid">`;
    b+=`<div class="stat"><span class="stat-val">${bg.tokens_used||0}</span><span class="stat-lbl">tokens (${pct}%)</span></div>`;
    b+=`<div class="stat"><span class="stat-val">${bg.clips_used||0}</span><span class="stat-lbl">clips</span></div>`;
    b+=`<div class="stat"><span class="stat-val">${bg.retakes_used||0}</span><span class="stat-lbl">retakes</span></div>`;
    if(rc.avg_critic_score) b+=`<div class="stat"><span class="stat-val">${rc.avg_critic_score.toFixed(1)}</span><span class="stat-lbl">avg score</span></div>`;
    if(bg.estimated_cost_usd>0) b+=`<div class="stat"><span class="stat-val">$${bg.estimated_cost_usd.toFixed(2)}</span><span class="stat-lbl">spent</span></div>`;
    b+=`</div>`;
    b+=budgetBlock('Tokens',bg.tokens_used,bg.token_budget);
    b+=budgetBlock('Clips',bg.clips_used,bg.clip_budget);
    if(rc.quality_arc&&rc.quality_arc.length){
      b+=`<div style="margin-top:0.6rem;font-size:0.7rem;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:0.04em">Quality Arc</div>`;
      rc.quality_arc.forEach(s=>{
        const c=s.score>=7?'var(--green)':s.score>=5?'var(--amber)':'var(--red)';
        b+=bar('Shot '+s.shot,s.score);
      });
    }
    b+=`</div>`;
  } else if(ev.kind==='production_failed'){
    b=`<strong style="color:var(--red)">FAILED:</strong> ${ev.reason||'unknown'}`;
  } else {
    b=JSON.stringify(ev).slice(0,150);
  }
  return hdr+`<div class="ev-body">${b}</div>`;
}

function bar(label,val){
  val=val||0;
  const pct=Math.min(100,val*10);
  const c=val>=7?'var(--green)':val>=5?'var(--amber)':'var(--red)';
  return `<div class="bar-row"><span class="bar-label">${label}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${c}"></div></div><span class="bar-val">${val.toFixed(1)}</span></div>`;
}

function budgetBlock(label,used,total){
  const pct=total?Math.min(100,used/total*100):0;
  return `<div class="budget-block"><div class="budget-track"><div class="budget-fill" style="width:${pct}%"></div></div><div class="budget-meta"><span>${label}</span><span>${used}/${total}</span></div></div>`;
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
