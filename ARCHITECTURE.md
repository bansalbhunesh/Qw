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
| `auteur/agents/cinematographer.py` | Wan t2v/i2v jobs, i2v continuity chaining with t2v fallback, download verification |
| `auteur/agents/sound.py` | CosyVoice TTS (character voices) + procedural mood-keyed score bed |
| `auteur/agents/editor.py` | Qwen-VL critic loop + audio overlay + crossfade assembly + score mix |
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
anchor = None                                     # previous shot's final frame
prev_frames = None                                # previous shot's frames for critic
for shot in shots:
    if not clip_budget: break
    try:
        prompt = inject(bible, shot.prompt)
        clip = wan.render(prompt, reference=anchor)  # i2v continuity, t2v fallback, retried
        frames = extract_frames(clip)             # ffmpeg -> data URIs
        score = qwen_vl.critique(shot, frames,    # 4-axis review (incl. cross-shot continuity)
                                 prev_frames)
        if governor.should_retake(score, shot.importance):
            clip = wan.render(prompt + critic.fix, reference=anchor)  # exactly one reshoot
        voice = cosyvoice.voice(shot.dialogue)    # smart speaker attribution
        prev_frames = extract_frames(clip, n=1)   # feed next critic
        anchor = extract_last_frame(clip)         # seed continuity for the next shot
        keep(clip, voice)
    except:
        log + skip (ship what we have)
cut = assemble(clips, dialogue, crossfade)        # silent-of-music cut
mood = composer(beat_tones)                        # grunt-tier mood pick
score = synth_pad(mood, duration(cut))             # procedural music bed
final.mp4 = mix(cut, score)                         # bed under dialogue
flush(ledger.json, manifest.json)
```

## Token-efficiency techniques (the "limited budget" criterion)

1. **Tiered routing** — `qwen-flash` for grunt work, `qwen-max` only for creative-critical beats.
2. **Asset caching** — one Style Bible, injected everywhere; no per-shot character re-description.
3. **Early-exit** — clips scoring >= threshold pass with zero reshoots.
4. **Importance-weighted retakes** — scarce reshoot budget spent on the hook first.
5. **Pre-flight gating** — refuse a call before paying if it would blow the ceiling.
6. **Real-money spend cap** — video is the only paid line item, so the Governor enforces a hard
   USD ceiling (`--max-spend-usd`): it stops rendering before a clip would exceed the cap, and
   `--estimate` previews best/worst-case cost without rendering. Clips are priced per resolution
   (`clip_price_usd`); mock runs price at zero (no real spend).

## 4-axis critic loop (the "multimodal orchestration" criterion)

The critic scores each rendered clip on four axes, not three:

| Axis | What it measures |
|------|-----------------|
| **prompt_adherence** | Does the rendered image match the intended shot? (composition, action, setting) |
| **character_consistency** | Do characters look as described? (age, clothing, features) |
| **shot_quality** | Cinematic quality — lighting, focus, framing, mood |
| **visual_continuity** | Does this shot feel like it belongs in the same film as the previous shot? |

The `visual_continuity` axis is the key innovation: the critic receives frames from BOTH the
current shot AND the previous shot, so it can catch character drift, wardrobe changes, or color
grade discontinuities between adjacent shots. The first shot scores 8/10 by default (no prior
reference). This closes a multimodal feedback loop that no linear pipeline can achieve.

## Visual continuity (the hardest problem in AI short drama)

Text-only character descriptions drift: the same prompt renders a different face shot to shot.
Auteur threads each shot's **final frame** into the next render as an image-to-video seed
(`Cinematographer.render(reference_image=...)`), so the character, costume, and world carry
forward *visually*, not just textually. If an i2v render fails (model unsupported, transient
error), it falls back to text-to-video automatically — continuity is an upgrade, never a
single point of failure. Toggle with `--no-consistency`.

## Sound design (most submissions ship none)

Two layers, both metered as first-class production stages:
- **Dialogue** — each shot's line is voiced with a per-character CosyVoice voice from the Bible.
- **Score** — a grunt-tier "composer" call reads the beat tones and picks one overall mood +
  intensity; `Sound.score()` then synthesizes a warm triad pad tuned to a mood-appropriate
  musical key (minor for dark beats, major for hope), softened with tremolo / low-pass / echo.
  It's mixed *under* the dialogue at low volume in the final cut. Procedural and offline, so it
  costs zero video/audio-model spend and never fails a render; the mood choice is the only LLM
  cost (a few hundred grunt-tier tokens).

## Resilience

- **Exponential-backoff retry** on all network calls (LLM, Wan, TTS, OSS) with jitter.
- **Partial-failure recovery** — individual shot failures are caught, logged, and skipped.
  A production ships whatever clips rendered successfully.
- **JSON repair** — on LLM parse failure, a repair prompt is issued to recover the response.
- **Vision fallback** — if Qwen-VL returns unparseable JSON, defaults to a safe neutral score.
- **Download verification** — Wan clips are checked for minimum file size after download.
- **Frame sampling robustness** — seeks past clip end are caught and skipped; fallback to first frame.
- **i2v → t2v fallback** — if image-to-video continuity fails, the shot still renders via t2v.
- **Voice isolation** — TTS failures never discard rendered clips; shots ship silent rather than
  being lost. Each shot's voice step is isolated from its render/critique pipeline.

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
- [x] Visual continuity: i2v frame-chaining for cross-shot character consistency (+ t2v fallback)
- [x] Score: AI-directed mood + procedural music bed mixed under dialogue
- [x] Test suite: 46 tests (budget, pipeline, media, sound, retry, LLM, benchmark)
- [x] Real-money spend guardrail: per-resolution clip pricing, hard USD cap, --estimate dry-run
- [x] Default to wan2.2-t2v-plus (free-tier available); wan2.7 paywalled via FreeTierOnly 403
- [x] Voice isolation: TTS failures no longer discard rendered clips
- [x] i2v OSS upload: anchor frames uploaded to DashScope's temp OSS bucket for Wan i2v API
- [x] CosyVoice v3-plus with English-compatible voices for international endpoint
- [x] TTS voice fallback fix: default to English-compatible `longshu` (was Chinese-only `longxiaochun`)
- [x] Expanded voice descriptor map: 17 Art Director voice types → CosyVoice ID mapping
- [x] Mock benchmark differentiation: critic/judge seed on shot-specific content, not system prompt
- [x] 4-axis critic: cross-shot visual continuity scoring (prev shot frames → critic for drift detection)
- [x] Smart dialogue voice attribution: speaker tag parsing, character name matching, parity fallback
- [x] Production report card in manifest (quality arc, budget utilization, cost summary)
- [x] Enhanced viewer: real-time critic verdicts (4-axis bars), retake decisions, budget status
- [x] Writer prompt engineering: contrast, specificity, subtext principles for stronger micro-dramas
- [x] Benchmark headline reframed: quality improvement + budget fraction (not misleading per-token ratio)
- [ ] Run the benchmark live; populate README table with real scores
- [ ] Deploy to Alibaba Cloud ECS; record proof-of-deployment video
- [ ] 3-min demo video + architecture diagram export + blog post
