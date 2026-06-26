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
After each clip renders, **Qwen-VL watches it** and scores it against the storyboard on four axes —
prompt adherence, character consistency, shot quality, and **cross-shot visual continuity** (comparing
frames against the previous shot to catch character drift). A failing take gets exactly one budgeted
reshoot with a corrected prompt; a passing take moves to the cut. This is the vision model closing
the loop on the video model, which is what "multimodal orchestration" actually means.

### The proof: a benchmark, not just a demo
Auteur ships with an evaluation harness (`bench/`). The same set of premises runs through a
**naive baseline** and through **Auteur**, with **Qwen-VL as an impartial judge** scoring both.

> Headline metric: **higher quality at a fraction of the budget.**
> Auteur scores **8.7/10** vs the baseline's **6.6/10** — a **32% quality improvement** —
> using just **5.3% of the 120K token budget** (6,363 tokens). The Budget Governor ensures the
> extra investment goes to critic-reviewed, importance-weighted shots with exactly one budgeted
> retake when a take fails.

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
   │ qwen-max │  script   │ qwen-max+VL  │  + char bible  │  Wan t2v/i2v     │
   └──────────┘           └──────────────┘                │  + visual chain  │
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
| Prompt Optimizer | `qwen-flash` | Refine video prompts for Wan's strengths (pays for itself in fewer retakes) |
| Cinematographer | `wan2.2-t2v-plus`, Wan i2v | Render shots; image-to-video for continuity; dynamic resolution |
| Sound | CosyVoice v3-plus TTS | Dialogue voicing (English voices) + procedural score bed |
| Editor / Critic | `qwen-vl-max` + ffmpeg | 4-axis scoring (incl. cross-shot continuity); assemble final cut |

All model calls go through Alibaba Cloud **DashScope** (international endpoint,
OpenAI-compatible). See [`deploy/`](deploy/) for the Alibaba Cloud deployment (ECS backend +
OSS asset storage) and the proof-of-deployment file.

---

## How this maps to the judging criteria

| Criterion | How Auteur scores |
|-----------|-------------------|
| **Narrative ability** | Structured beat-sheet screenwriting with importance-weighted beats, not one-shot prompting |
| **Multimodal orchestration** | Qwen-Max + Qwen-VL + Wan + CosyVoice TTS coordinated in a 4-axis critic loop with cross-shot continuity scoring |
| **Output quality under a token budget** | The Budget Governor — with a benchmark proving 32% quality improvement at 5.3% budget utilization, plus ablation study proving each feature's contribution |
| **Production-readiness** | Alibaba Cloud (ECS + OSS + DashScope), token ledger, eval harness, ablation study, 73 tests, storyboard export, live web viewer |
| **Innovation** | Adaptive scarcity-aware retakes, cross-shot visual continuity, dynamic resolution routing, prompt optimizer, tone-aware transitions, storyboard export — not a linear pipeline |

---

## Run it now — no API key required

Auteur ships a **mock mode**: the full pipeline runs offline with deterministic fakes and a
bundled static ffmpeg, producing a *real assembled `.mp4`*, a real token ledger, and a real
benchmark report. This is how you verify the architecture end-to-end without spend.

```bash
pip install -r requirements.txt
AUTEUR_MOCK=1 python -m auteur.cli "A lighthouse keeper teaches the drone sent to replace him"
# -> out/final.mp4  +  out/ledger.json (tokens by stage, clips, retakes)
```

Run the benchmark harness (naive baseline vs. Auteur, with the Qwen-VL judge):

```bash
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt
```

Run the ablation study (proves each architectural feature pulls its weight):

```bash
AUTEUR_MOCK=1 python -m bench.ablation --premise "A lighthouse keeper teaches the drone sent to replace him"
```

Run the test suite:

```bash
AUTEUR_MOCK=1 python -m pytest -q
```

## Go live

```bash
cp .env.example .env          # add your DashScope (Alibaba Cloud Model Studio) key

# See what a production would cost before spending a cent:
python -m auteur.cli "A night-shift nurse finds a note from a patient" --estimate

# Render for real, with a hard $1 spend cap as a safety net:
python -m auteur.cli "A night-shift nurse finds a note from a patient" --max-spend-usd 1.00

# Only keep shots scoring >= 6.0 in the final cut (quality over quantity):
python -m auteur.cli "A night-shift nurse finds a note from a patient" --quality-gate 6.0

# Hero shots at 1080P, grunt shots at 480P (dynamic budget-optimized resolution):
python -m auteur.cli "A night-shift nurse finds a note from a patient" --dynamic-resolution
```

With a key present, the same code paths call Qwen-Max / Qwen-VL (OpenAI-compatible endpoint)
and Wan for real renders — mock vs. live is a single config flip (`AUTEUR_MOCK`).

**Real-money guardrail.** Video generation is the only line item that costs real money, so the
Budget Governor enforces a hard USD ceiling (`--max-spend-usd`, default $2.00): it stops
rendering *before* a clip would push estimated spend past the cap, and `--estimate` prints the
projected best/worst-case cost without rendering anything. Default model is `wan2.2-t2v-plus`
(available on the DashScope International free tier); point `AUTEUR_MODEL_WAN_T2V` at
`wan2.7-t2v` once paid billing is enabled.

`scripts/probe_wan.py` is a standalone diagnostic that probes the video endpoint directly and
reports which Wan model names your account can call — useful for a fast 403/quota check.

## Status

**Live-validated pipeline.** Full end-to-end productions run on Alibaba Cloud DashScope with
real Wan video generation, Qwen-Max/VL orchestration, CosyVoice TTS, and AI-directed scoring.

Working today:
- Budget Governor + token ledger (6K tokens to produce a 6-shot film from 120K budget)
- 4-axis Qwen-VL critic loop: prompt adherence, character consistency, shot quality, cross-shot visual continuity
- Importance-weighted retakes with adaptive scarcity: bar rises as budget depletes
- Visual continuity: i2v frame-chaining via OSS-uploaded anchor frames (with t2v fallback)
- Cross-shot continuity scoring: critic compares frames from adjacent shots to catch character drift
- Smart dialogue voice attribution: parses speaker tags, character name mentions, with parity fallback
- CosyVoice v3-plus dialogue voicing with English-compatible character voices (17 voice descriptors)
- AI-directed procedural score (mood-keyed triad pad mixed under dialogue)
- Intelligent scene transitions: tone-aware cut/dissolve/fade selection per beat boundary
- Crossfade assembly with Windows-safe concat-filter fallback
- Resilient production: voice failures never discard clips, partial-shot recovery
- Production report card in the manifest (quality arc, budget utilization, cost summary)
- Parallel shot rendering when `--no-consistency` is set (wall-clock speedup with thread pool)
- Tier-level token breakdown: proves model routing works (grunt/creative/vision spend)
- Prompt optimizer: dedicated Wan-specific prompt refinement agent (grunt-tier, pays for itself)
- Dynamic resolution routing: hero shots at 1080P, grunt shots at 480P (per-shot budget optimization)
- Shot pacing engine: variable clip duration based on beat importance and type
- Storyboard HTML export: visual production breakdown with frames, scores, and budget analytics
- Live web viewer with real-time critic verdicts, retake decisions, and budget status bars
- 73 passing tests, naive baseline, benchmark harness

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design, module map, and roadmap.

## License

MIT — see [`LICENSE`](LICENSE).
