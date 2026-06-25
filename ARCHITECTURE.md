# Auteur — Architecture & Build Roadmap

## Design principle

A production is a **constrained optimization**: maximize the Qwen-VL judge's quality score
subject to a hard token + clip budget. Every component exists to push that frontier. The
Budget Governor (`auteur/budget.py`) is the optimizer's accountant; the agents are its workers.

## Module map

| Module | Responsibility |
|--------|----------------|
| `auteur/config.py` | Model IDs, DashScope endpoints, tier→model map, budget defaults |
| `auteur/budget.py` | **Budget Governor** — metering, gates, retake economics, token ledger |
| `auteur/llm.py` | Metered Qwen client (chat + Qwen-VL vision), tier routing, lenient JSON |
| `auteur/models.py` | Shared data structures (Beat, Shot, Script, StyleBible, Production) |
| `auteur/agents/writer.py` | Premise → beat sheet → scripted shots (structured) |
| `auteur/agents/art_director.py` | Character & Style Bible (cached, injected into every prompt) |
| `auteur/agents/cinematographer.py` | Wan2.7 text/image-to-video async jobs |
| `auteur/agents/sound.py` | CosyVoice TTS for dialogue + music cues |
| `auteur/agents/editor.py` | Qwen-VL critic loop + ffmpeg assembly |
| `auteur/agents/showrunner.py` | Orchestrator — runs the budgeted control loop |
| `deploy/alibaba_cloud.py` | OSS storage + DashScope + FastAPI service (Alibaba Cloud proof) |
| `bench/` | Naive-vs-Auteur benchmark with Qwen-VL-as-judge |

## The budgeted control loop

```
write(premise) -> script (beats carry importance)
build_bible(script) -> StyleBible (cached once)
for shot in shots:
    if not clip_budget: break
    prompt = inject(bible, shot.prompt)
    clip = wan.render(prompt)
    score = qwen_vl.critique(shot, frames(clip))
    if governor.should_retake(score, shot.importance):   # importance-weighted
        clip = wan.render(prompt + critic.fix)            # exactly one reshoot
    keep(clip); voice(shot.dialogue)
assemble(approved_clips) -> final.mp4
flush(ledger.json)
```

## Token-efficiency techniques (the "limited budget" criterion)

1. **Tiered routing** — `qwen-flash` for grunt work, `qwen-max` only for creative-critical beats.
2. **Asset caching** — one Style Bible, injected everywhere; no per-shot character re-description.
3. **Early-exit** — clips scoring ≥ threshold pass with zero reshoots.
4. **Importance-weighted retakes** — scarce reshoot budget spent on the hook first.
5. **Pre-flight gating** — refuse a call before paying if it would blow the ceiling.

## Build roadmap (to July 10)

- [x] Repo skeleton, budget economy, agent interfaces, Alibaba Cloud proof, benchmark contract
- [ ] Wire `DASHSCOPE_API_KEY`; validate Wan2.7 async request/response shapes live
- [ ] Harden frame sampling (ffmpeg) + OSS upload round-trip
- [ ] Implement CosyVoice TTS call + music bed
- [ ] Implement the `NaiveShowrunner` baseline for the benchmark
- [ ] Run the benchmark over `bench/premises.txt`, populate README table
- [ ] Deploy `deploy/alibaba_cloud.py` to ECS; record the proof video
- [ ] Polish: web viewer that streams production steps for the demo
- [ ] 3-min demo video + architecture diagram export + (optional) blog post
```
