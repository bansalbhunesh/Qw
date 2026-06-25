# Auteur — The Budget-Aware AI Showrunner

> An autonomous agent that turns a one-line premise into a finished vertical short drama —
> and directs like a real showrunner: it nails the shot without wasting film.
>
> **Track 2: AI Showrunner** · Global AI Hackathon Series with Qwen Cloud

---

## The thesis

Most short-drama agents are a straight line: `premise → script → generate every shot → stitch`.
They burn tokens blindly and hope the output is good. Track 2 explicitly asks builders to
**"maximize output quality under a limited token budget"** — and almost nobody engineers for it.

**Auteur** treats a production like a real director does: a fixed budget, hard creative
priorities, and a review of the dailies before anything ships. Two systems make it different:

### 1. The Budget Governor — a real token economy
- **Tiered model routing.** Cheap Qwen (Flash/Turbo) handles grunt work — shot-list formatting,
  prompt cleanup. `qwen-max` is reserved for the creative-critical beats: the hook, the dialogue,
  the final cut decisions.
- **Asset caching.** The Character & Style Bible is generated once and reused across every shot,
  instead of re-describing characters per prompt.
- **Importance-weighted retakes.** Reshoot budget is spent on the highest-impact shots first
  (the opening hook earns more retakes than a B-roll cutaway).
- **Early-exit.** When the critic's quality score clears threshold, the shot passes — no wasted
  reshoots.
- Every production emits a **token ledger** (`ledger.json`): who spent what, on which beat, and why.

### 2. The Qwen-VL critic loop — multimodal orchestration, not fire-and-forget
After each clip renders, **Qwen-VL watches it** and scores it against the storyboard on three axes —
prompt adherence, character consistency, shot quality. A failing take gets exactly one budgeted
reshoot with a corrected prompt; a passing take moves to the cut. This is the vision model closing
the loop on the video model, which is what "multimodal orchestration" actually means.

### The proof: a benchmark, not just a demo
Auteur ships with an evaluation harness (`bench/`). The same set of premises runs through a
**naive baseline** and through **Auteur**, with **Qwen-VL as an impartial judge** scoring both.

> Headline metric (target): **~92% of the baseline's quality at ~45% of the tokens.**

In a field where ~95% of submissions are demos with zero evaluation, a real benchmark is the
single cheapest signal of production-grade engineering — which is exactly what these judges said
they reward.

---

## Architecture

```
                          ┌──────────────────────────────────────────┐
                          │            SHOWRUNNER (orchestrator)        │
   premise ──────────────▶│   plans the production · owns the budget   │
                          │   routes models · enforces the policy      │
                          └───────┬───────────────────────────┬────────┘
                                  │                            │  Budget Governor
                                  ▼                            │  (token ledger)
   ┌──────────┐   beats   ┌──────────────┐  shot prompts  ┌────▼─────────────┐
   │  WRITER  │──────────▶│ ART DIRECTOR │───────────────▶│ CINEMATOGRAPHER  │
   │ qwen-max │  script   │ qwen-max+VL  │  + char bible  │  Wan2.7-t2v /    │
   └──────────┘           └──────────────┘                │  Wan image2video │
                                                          └────────┬─────────┘
                                  ┌─────────────┐  dialogue        │ raw clips
                                  │    SOUND    │  + music cues     ▼
                                  │  TTS (Qwen) │──────────▶┌───────────────────┐
                                  └─────────────┘           │  EDITOR / CRITIC   │
                                                            │  Qwen-VL reviews   │
                                  retake? ◀──── fail ───────│  each clip, then   │
                                                  pass ────▶│  ffmpeg assembles  │
                                                            └─────────┬─────────┘
                                                                      ▼
                                                            vertical short (.mp4)
```

| Stage | Model(s) | Role |
|-------|----------|------|
| Showrunner | `qwen-max` (plan) · `qwen-flash` (routing) | Budget + orchestration |
| Writer | `qwen-max` | Premise → logline → beat sheet → scripted shots (structured JSON) |
| Art Director | `qwen-max` + `qwen-vl-max` | Character & Style Bible for cross-shot consistency |
| Cinematographer | `wan2.7-t2v`, Wan image-to-video | Render shots; image-to-video for continuity |
| Sound | Qwen TTS / CosyVoice | Dialogue voicing + music/SFX cues |
| Editor / Critic | `qwen-vl-max` + ffmpeg | Watch, score, retake-or-pass; assemble final cut |

All model calls go through Alibaba Cloud **DashScope** (international endpoint,
OpenAI-compatible). See [`deploy/`](deploy/) for the Alibaba Cloud deployment (ECS backend +
OSS asset storage) and the proof-of-deployment file.

---

## How this maps to the judging criteria

| Criterion | How Auteur scores |
|-----------|-------------------|
| **Narrative ability** | Structured beat-sheet screenwriting, not one-shot prompting |
| **Multimodal orchestration** | Qwen-Max + Qwen-VL + Wan + TTS coordinated in a critic loop |
| **Output quality under a token budget** | The Budget Governor — with a benchmark proving the trade-off |
| **Production-readiness** | Alibaba Cloud (ECS + OSS + DashScope), token ledger, eval harness, clean repo |
| **Innovation** | A self-critiquing, budget-aware director — not a linear pipeline |

---

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # add your DashScope API key
python -m auteur.cli "A night-shift nurse finds a note from a patient who left years ago"
```

Run the benchmark (naive baseline vs. Auteur):

```bash
python -m bench.benchmark --premises bench/premises.txt
```

## Status

This repository is an active hackathon build. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
detailed design and the build roadmap.

## License

MIT — see [`LICENSE`](LICENSE).
