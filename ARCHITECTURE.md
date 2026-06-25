# Auteur — Architecture & Build Roadmap

## Design principle

A production is a **constrained optimization**: maximize the Qwen-VL judge's quality score
subject to a hard token + clip budget. Every component exists to push that frontier. The
Budget Governor (`auteur/budget.py`) is the optimizer's accountant; the agents are its workers.

## Module map

| Module | Responsibility |
|--------|----------------|
| `auteur/config.py` | Model IDs, DashScope endpoints, tier-to-model map, budget defaults |
| `auteur/budget.py` | **Budget Governor** — metering, hard gates, importance-weighted retake economics, ledger |
| `auteur/llm.py` | Metered Qwen client: tiered routing, JSON parse + repair, vision fallback |
| `auteur/transport.py` | Pluggable LLM transport (live OpenAI/DashScope vs. deterministic MockTransport) |
| `auteur/media.py` | ffmpeg: clip synthesis, frame sampling, audio overlay, crossfade assembly, duration probe |
| `auteur/retry.py` | Exponential-backoff retry with jitter for all network calls |
| `auteur/events.py` | Thread-safe event bus for the live web viewer |
| `auteur/log.py` | Structured production logging |
| `auteur/models.py` | Data structures (Beat, Shot, Script, StyleBible, Production) |
| `auteur/agents/writer.py` | Premise → beat sheet → cinematic shot-level script (structured JSON) |
| `auteur/agents/art_director.py` | Character & Style Bible — one generation, cached across every shot |
| `auteur/agents/cinematographer.py` | Wan2.7 t2v/i2v async jobs with retry, download verification |
| `auteur/agents/sound.py` | CosyVoice TTS async API with retry, character voice mapping |
| `auteur/agents/editor.py` | Qwen-VL critic loop + audio overlay + crossfade assembly |
| `auteur/agents/showrunner.py` | Orchestrator — budgeted control loop, partial-failure recovery, manifest |
| `auteur/baseline.py` | NaiveShowrunner — the A/B baseline (no routing, no caching, no critic) |
| `auteur/viewer.py` | Live web viewer — SSE streaming of production events for the demo |
| `auteur/cli.py` | CLI entrypoint with structured output |
| `deploy/alibaba_cloud.py` | OSS upload, DashScope health check, FastAPI service (ECS proof) |
| `Dockerfile` | Production container with system ffmpeg + health check |
| `bench/` | Benchmark harness: both systems + Qwen-VL judge + efficiency report |

## The budgeted control loop

```
write(premise) -> script (beats carry importance + tone)
build_bible(script) -> StyleBible (cached once)
for shot in shots:
    if not clip_budget: break
    try:
        prompt = inject(bible, shot.prompt)
        clip = wan.render(prompt)                 # retried on transient failure
        frames = extract_frames(clip)             # ffmpeg -> data URIs
        score = qwen_vl.critique(shot, frames)    # 3-axis review
        if governor.should_retake(score, shot.importance):
            clip = wan.render(prompt + critic.fix)   # exactly one reshoot
        voice = cosyvoice.voice(shot.dialogue)
        keep(clip, voice)
    except:
        log + skip (ship what we have)
assemble(clips, audio, crossfade) -> final.mp4
flush(ledger.json, manifest.json)
```

## Token-efficiency techniques (the "limited budget" criterion)

1. **Tiered routing** — `qwen-flash` for grunt work, `qwen-max` only for creative-critical beats.
2. **Asset caching** — one Style Bible, injected everywhere; no per-shot character re-description.
3. **Early-exit** — clips scoring >= threshold pass with zero reshoots.
4. **Importance-weighted retakes** — scarce reshoot budget spent on the hook first.
5. **Pre-flight gating** — refuse a call before paying if it would blow the ceiling.

## Resilience

- **Exponential-backoff retry** on all network calls (LLM, Wan, TTS, OSS) with jitter.
- **Partial-failure recovery** — individual shot failures are caught, logged, and skipped.
  A production ships whatever clips rendered successfully.
- **JSON repair** — on LLM parse failure, a repair prompt is issued to recover the response.
- **Vision fallback** — if Qwen-VL returns unparseable JSON, defaults to a safe neutral score.
- **Download verification** — Wan clips are checked for minimum file size after download.
- **Frame sampling robustness** — seeks past clip end are caught and skipped; fallback to first frame.

## Mock mode

`AUTEUR_MOCK` (auto-on when no key) swaps two seams without touching agent logic:
- **LLM**: `MockTransport` returns deterministic, stage-appropriate JSON. Critic scores are
  seeded to vary, so some shots fail and the retake economics genuinely run.
- **Media**: `make_placeholder_clip` synthesizes real per-shot ffmpeg clips; frame sampling,
  audio overlay, and crossfade assembly are the *same code* used live.

## Build roadmap (to July 10)

- [x] Repo skeleton, budget economy, agent interfaces, Alibaba Cloud proof, benchmark contract
- [x] Mock-mode pipeline: runs end-to-end offline, produces a real `.mp4` + ledger + manifest
- [x] Frame sampling, Qwen-VL critic loop, data-URI frames, crossfade transitions
- [x] NaiveShowrunner baseline + functional benchmark harness + Qwen-VL judge
- [x] Retry infrastructure (exponential backoff + jitter on all network calls)
- [x] Partial-failure recovery in the showrunner (ship what we have)
- [x] JSON parse repair (LLM re-prompt on malformed JSON)
- [x] Full CosyVoice TTS integration (DashScope async API + character voice mapping)
- [x] Audio overlay (dialogue layered onto clips before assembly)
- [x] Production manifest (`manifest.json` — script, shots, scores, paths, budget)
- [x] Structured logging across all agents
- [x] Event bus + live web viewer (SSE streaming for the demo video)
- [x] Dockerfile with system ffmpeg + health check
- [x] Test suite: 30 tests (budget, pipeline, media, retry, LLM, benchmark)
- [ ] Wire `DASHSCOPE_API_KEY`; validate Wan2.7 / CosyVoice request shapes live
- [ ] OSS round-trip validation with real bucket
- [ ] Run the benchmark live; populate README table with real scores
- [ ] Deploy to Alibaba Cloud ECS; record proof-of-deployment video
- [ ] 3-min demo video + architecture diagram export + blog post
