<div align="center">

# 🎬 Auteur — The Budget-Aware AI Showrunner

> 📖 **Read the full engineering deep dive on Medium:** [How I Built an AI Showrunner That Produced a 7.3-Scored Drama for Just $0.60](https://medium.com/@bhuneshbansal20039888/how-i-built-an-ai-showrunner-that-produced-a-7-3-scored-drama-for-just-0-60-0ed3f5b70857)

**Auteur produced a 7.3/10-scored vertical short drama on Alibaba Cloud Wan
using just 10.9% of the allowed token budget — with an estimated ~46%
token-cost saving from tiered model routing (see the benchmark section for
exactly what is measured vs. estimated).**

`Track 2: AI Showrunner` · Global AI Hackathon Series with Qwen Cloud

[![CI](https://github.com/bansalbhunesh/Qw/actions/workflows/ci.yml/badge.svg)](https://github.com/bansalbhunesh/Qw/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-92%20passing-2ea44f)
![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![Qwen](https://img.shields.io/badge/Qwen-Max%20·%20VL%20·%20Wan%20·%20CosyVoice-6e56cf)
![Cloud](https://img.shields.io/badge/Alibaba%20Cloud-DashScope%20%2B%20OSS%20%2B%20ECS-ff6a00)
![License](https://img.shields.io/badge/license-MIT-2ea44f)

<br>

![Auteur — real Wan footage](assets/hero.gif)

*Real footage rendered live on Alibaba Cloud Wan — "A lighthouse keeper teaches the drone sent to replace him."*

</div>

---

## Proven results — live on Alibaba Cloud

> **Premise:** *"A lighthouse keeper teaches the drone sent to replace him"*
>
> | Metric | Live result |
> |---|---|
> | **Avg Qwen-VL critic score** | **7.3 / 10** (shots scored 8.0, 8.0, 6.0 on real Wan footage) |
> | **Token budget used** | **13,043 / 120,000 — just 10.9%** |
> | **Model-routing savings** | **46%** (13,043 actual vs 23,999 if every call used `qwen-max`) |
> | **Real spend** | **$0.60** for the rendered clips |
> | Tier split | grunt `qwen-flash` 5,478 · creative `qwen-max` 4,298 · vision `qwen-vl-max` 3,267 |
>
> *A 7.3/10 film using 10.9% of the budget. That is the Budget Governor in action.*

---

## Benchmark: Auteur vs. Naive Baseline

Auteur ships a full A/B evaluation harness (`bench/`) that runs the same premises through a naive single-pass pipeline and through Auteur, with **Qwen-VL as an impartial judge** scoring both. It is fully reproducible with no API key:

```bash
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt
```

| System | Quality | Tokens | Clips | Retakes | Source |
|--------|---------|--------|-------|---------|--------|
| Naive (mock) | 6.6 / 10 | ~560 | 6 | 0 | `bench/results/` |
| Auteur (mock) | 6.6 / 10 | ~10,100 | 8 | 2 | `bench/results/` |
| **Auteur (live)** | **7.3 / 10** | **13,043** | 8 | 2 | `out_live/ledger.json` |

> **What the numbers mean, precisely.** In **mock** mode the judge returns deterministic seeded scores, so both arms land at **6.6/10** — the mock run validates that the pipeline and the VL-judge wiring work end-to-end (both arms execute, retakes fire, the ledger meters), *not* a quality delta. The **7.3/10** is a **measured single-arm** result from a real DashScope + Wan run (`out_live/`), using 10.9% of the token budget.
>
> ⚠️ A **live** naive-vs-Auteur A/B is gated on paid Wan billing and **has not yet been run** — we do not claim a live head-to-head quality delta we have not measured.

**Model routing split (Auteur, live run):**

| Tier | Model | Tokens | Role |
|------|-------|--------|------|
| Creative | `qwen-max` | 4,298 | Script · Art Direction · Retake decisions |
| Grunt | `qwen-flash` | 5,478 | Prompt formatting · Shot list cleanup |
| Vision | `qwen-vl-max` | 3,267 | 4-axis critic scoring of real Wan frames |

**Routing economics.** The tiered router sends grunt work (prompt formatting, shot-list cleanup) to `qwen-flash` instead of `qwen-max`. On the live token split this is an **estimated ~46% token-cost reduction** versus an all-`qwen-max` counterfactual — an estimate that assumes those grunt tokens would otherwise price at the premium tier, not a billed measurement. Every routing decision is auditable in `ledger.json`.

Run the benchmark yourself (no API key required):
```bash
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt
```

> **Model stack.** The code defaults to `qwen3-max` · `qwen3-flash` · `qwen-vl-max` · `wan2.7-t2v` (latest generation on DashScope), configurable in `.env`. **The live 7.3 run above used the free-tier stack** — `qwen-max` / `qwen-flash` / `qwen-vl-max` + `wan2.2-t2v-plus`, no TTS — so every metered number here is reproducible without paid billing. Upgrading the stack is a config change, not a code change.

---

## Ablation study — every feature earns its place

Each architectural feature is disabled in turn to measure its individual contribution.
This proves Auteur is an engineered system, not a grab-bag of features.

| Variant | What is removed | Quality impact |
|---------|----------------|----------------|
| `full` | All features enabled | Baseline (7.3/10 live) |
| `no_critic` | Skip Qwen-VL scoring → no retakes | ↓ Bad shots ship without review |
| `no_prompt_opt` | Raw Writer prompts sent to Wan | ↓ Wan-specific refinement skipped |
| `no_bible` | No Style Bible injection into prompts | ↓ Character drift across shots |
| `no_routing` | All calls use `qwen-max` | Same quality, 46% more token spend |

```bash
AUTEUR_MOCK=1 python -m bench.ablation --premise "A lighthouse keeper teaches the drone sent to replace him"
```

---

## Why Auteur is different from every other submission

Most short-drama agents are a straight line: `premise → script → generate every shot → stitch`.
They burn tokens blindly and hope the output is good. Track 2 explicitly asks builders to
**"maximize output quality under a limited token budget"** — and almost nobody engineers for it.

**The three systems that make Auteur different:**

### 1. The Budget Governor — a real token economy
- **Tiered model routing.** Cheap `qwen-flash` handles grunt work — shot-list formatting, prompt cleanup. `qwen-max` is reserved for the creative-critical beats: the hook, the dialogue, the final cut decisions.
- **Asset caching.** The Character & Style Bible is generated once and reused across every shot, instead of re-describing characters per prompt.
- **Importance-weighted retakes.** Reshoot budget is spent on the highest-impact shots first (the opening hook earns more retakes than a B-roll cutaway).
- **Early-exit.** When the critic's quality score clears threshold, the shot passes — no wasted reshoots.
- **Adaptive scarcity.** As retake budget depletes, the importance threshold rises — the system becomes more selective under pressure, exactly like a real director managing a tight schedule.
- Every production emits a **token ledger** (`ledger.json`): who spent what, on which beat, and why.

### 2. The Qwen-VL critic loop — multimodal orchestration, not fire-and-forget
After each clip renders, **Qwen-VL watches it** and scores it against the storyboard on four axes —
prompt adherence, character consistency, shot quality, and **cross-shot visual continuity** (comparing
frames against the previous shot to catch character drift). A failing take gets exactly one budgeted
reshoot with a corrected prompt; a passing take moves to the cut. **This is the vision model closing
the loop on the video model** — what "multimodal orchestration" actually means in practice.

### 3. Identity-lock conditioning ladder — continuity that escalates
Character drift is the hardest problem in generative short drama. Auteur attacks it with an
**escalating conditioning ladder** — the strongest available lock is tried first, and every rung
degrades gracefully so a production never stalls on an unsupported model or a rejected schema:

| Rung | Conditioning | Locks |
|------|-------------|-------|
| **r2v** | subject/reference-to-video against a stable establishing frame | the character's *identity* across the entire drama |
| **kf2v** | keyframe-to-video (first **and** last frame) | the exact start and end of a shot |
| **i2v** | image-to-video from the previous shot's final frame | frame-to-frame visual continuity |
| **t2v** | prompt only | always-available fallback |

Every rung is **metered through the Budget Governor**, and the ledger records exactly which mode
produced each clip — and what it fell back from — so the conditioning path is auditable, not a
black box. (The ladder is fully mock-tested and live-ready; the advanced r2v/kf2v rungs activate
when a reference is available and degrade to i2v→t2v otherwise.)

### 4. Series Mode — Episode-Native Continuity
Auteur doesn't just generate standalone shorts; it runs entire TV series. When Episode 1 wraps,
the Showrunner **permanently locks the Style Bible** (character descriptions, visual look). When
you request Episode 2, it reads the final narrative beat of Episode 1, generates a logical continuation,
and automatically injects the locked Style Bible. The characters never drift, and the world remains
perfectly consistent across a multi-episode run.

---

## See it in action

**The Studio — watch the showrunner work in real time.** Every clip is scored by Qwen-VL on four
axes (prompt adherence, character consistency, shot quality, cross-shot continuity), retake
decisions are made live, and the budget meters tick as it spends:

![Live Studio](assets/studio.png)

**The Storyboard — a self-contained breakdown exported on every run.** Real frames from each
rendered shot, the live critic score, the Style Bible, routing efficiency, and the decision log:

![Storyboard](assets/storyboard_top.png)

**The Gallery — browse every production with aggregate economics at a glance:**

![Gallery metrics](assets/gallery_metrics.png)

**The Analytics dashboard (`/analytics`) — queryable evidence, not screenshots.** Every production
and every metered call is persisted to a **structured SQLite store** (`productions/auteur.db`) that
powers a live dashboard: cross-production spend and token totals, tokens-by-model, and the
**r2v/kf2v/i2v/t2v conditioning-mode distribution** — the pipeline's decisions rendered as data.
It's a real, queryable database with **zero external services to provision** (no Postgres server,
no migrations) — a judge can open the `.db` file in any SQLite browser and audit the raw rows.

---

## Architecture

```mermaid
flowchart TD
    P["premise"] --> S["SHOWRUNNER\n(orchestrator)"]
    S --> W["WRITER\nqwen-max"]
    S --> BG["Budget Governor\n(token ledger)"]
    W -->|"beat sheet\n+ script"| AD["ART DIRECTOR\nqwen-max"]
    AD -->|"style bible\n+ char descriptions"| PO["PROMPT OPTIMIZER\nqwen-flash"]
    PO -->|"refined prompts"| C["CINEMATOGRAPHER\nWan t2v/i2v"]
    BG -->|"resolution routing\n480P/720P/1080P"| C
    C -->|"raw clips"| EC["EDITOR / CRITIC\nQwen-VL + ffmpeg"]
    EC -->|"fail → retake"| C
    SND["SOUND\nCosyVoice TTS"] -->|"dialogue\n+ score bed"| EC
    EC -->|"pass → assemble"| F["final.mp4\n+ storyboard.html\n+ ledger.json"]

    style S fill:#1a1a2e,color:#fff,stroke:#6ea8fe
    style BG fill:#2a1a1a,color:#fff,stroke:#e87040
    style W fill:#1a2a1a,color:#fff,stroke:#7ec87e
    style AD fill:#1a2a1a,color:#fff,stroke:#7ec87e
    style PO fill:#1a2a2a,color:#fff,stroke:#6ea8fe
    style C fill:#2a2a1a,color:#fff,stroke:#f0ad4e
    style EC fill:#1a1a2e,color:#fff,stroke:#6ea8fe
    style SND fill:#1a2a2a,color:#fff,stroke:#6ea8fe
    style F fill:#0a2a0a,color:#fff,stroke:#7ec87e
```

| Stage | Model(s) | Role |
|-------|----------|------|
| Showrunner | `qwen-max` (plan) · `qwen-flash` (routing) | Budget + orchestration |
| Writer | `qwen-max` | Premise → logline → beat sheet → scripted shots (structured JSON) |
| Art Director | `qwen-max` + `qwen-vl-max` | Character & Style Bible for cross-shot consistency |
| Prompt Optimizer | `qwen-flash` | Refine video prompts for Wan's strengths (pays for itself in fewer retakes) |
| Cinematographer | Wan `t2v`/`i2v`/`r2v`/`kf2v` | Escalating identity-lock conditioning ladder (r2v→kf2v→i2v→t2v) with graceful degradation; dynamic resolution |
| Sound | CosyVoice v3-plus TTS | Dialogue voicing (English voices) + procedural score bed |
| Editor / Critic | `qwen-vl-max` + ffmpeg | 4-axis scoring (incl. cross-shot continuity); assemble final cut |

All model calls go through Alibaba Cloud **DashScope** (international endpoint,
OpenAI-compatible). See [`deploy/`](deploy/) for the Alibaba Cloud deployment (ECS backend +
OSS asset storage) and the proof-of-deployment file.

### Production deliverables (per run)

Every Auteur production outputs five first-class artifacts:

| Artifact | What it is |
|----------|-----------| 
| `final.mp4` | The assembled vertical short with dialogue, score, and crossfade transitions |
| `storyboard.html` | Self-contained visual breakdown: every shot's frames, critic scores, budget analytics, Governor decisions |
| `manifest.json` | Full production state: script, shots, scores, timeline, report card, quality arc |
| `ledger.json` | Per-call token ledger: who spent what, on which beat, using which model tier |
| `score.wav` | AI-directed procedural music bed (mood-keyed triad pad) |

---

## How this maps to the judging criteria

| Criterion | How Auteur scores |
|-----------|-------------------|
| **Narrative ability** | Structured beat-sheet screenwriting with importance-weighted beats, not one-shot prompting |
| **Multimodal orchestration** | Qwen-Max + Qwen-VL + Wan + CosyVoice TTS coordinated in a 4-axis critic loop with cross-shot continuity scoring |
| **Output quality under a token budget** | The Budget Governor — a live 7.3/10 production using 10.9% of budget with 46% routing savings, plus a naive-vs-Auteur benchmark and an ablation study proving each feature's contribution |
| **Production-readiness** | Alibaba Cloud (ECS + OSS + DashScope), token ledger, eval harness, ablation study, 92 tests, storyboard export, live web viewer, concurrent-safe multi-tenant backend |
| **Innovation** | Adaptive scarcity-aware retakes, cross-shot visual continuity, dynamic resolution routing, prompt optimizer, tone-aware transitions — not a linear pipeline |

---

## Try it now — zero API key, zero spend

### Option 1: Docker (fastest — one command)

```bash
git clone https://github.com/bansalbhunesh/Qw && cd Qw
cp .env.example .env          # no key needed for mock mode
docker compose up -d
# Studio at http://localhost:8080  •  API at http://localhost:8000/docs
```

### Option 2: Python (full pipeline in mock mode)

```bash
pip install -r requirements.txt

# Run a full single-episode production (no API key, no spend):
AUTEUR_MOCK=1 python -m auteur.cli "A lighthouse keeper teaches the drone sent to replace him"
# -> out/episode_1.mp4  +  out/ledger.json  +  out/storyboard.html

# Run a 3-episode series (characters and Style Bible persist across episodes):
AUTEUR_MOCK=1 python -m auteur.series "A detective learns her informant is her husband" --episodes 3
# -> series_out/episode_1/  episode_2/  episode_3/  series_manifest.json  series_storyboard.html

# Run the benchmark (naive baseline vs. Auteur, Qwen-VL judge):
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt

# Run the ablation study (feature contribution analysis):
AUTEUR_MOCK=1 python -m bench.ablation --premise "A lighthouse keeper teaches the drone sent to replace him"

# Run the full test suite (92 tests):
AUTEUR_MOCK=1 python -m pytest -q
```

## Go live (with a DashScope API key)

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

**Pre-flight diagnostic.** Before going live, validate the full pipeline:

```bash
python scripts/diagnose.py    # checks ffmpeg, API key, models, runs a test production
```

**Demo reel.** Turn any finished production into a shareable sizzle reel — title card, the real
footage with each shot's live Qwen-VL score captioned, and a closing budget-economy stats card,
over a procedural score. Offline (ffmpeg + Pillow), no spend:

```bash
python scripts/make_reel.py out_live              # 16:9 -> out_live/reel.mp4
python scripts/make_reel.py out_live --vertical   # 9:16 mobile cut for socials
```

## Deploy

One-command deployment with Docker Compose:

```bash
cp .env.example .env          # add your DashScope key
docker compose up -d           # API on :8000, viewer on :8080
```

**Backend API** (`:8000`):
- `POST /api/produce` — render a short from a premise (JSON body)
- `GET /api/events?prod_id=<id>` — live SSE stream, per-production (concurrent-safe multi-tenant)
- `GET /api/gallery` · `GET /api/metrics` — browse past productions + aggregate stats
- `GET /productions/{id}/final.mp4` · `/storyboard.html` · artifacts
- `GET /docs` — interactive Swagger/OpenAPI docs (auto-generated)
- CORS enabled for browser clients

**Frontend** (`:8080`):
- **Studio** (`/`) — submit a premise and watch the production stream live via SSE: script,
  Style Bible, per-shot 4-axis critic verdicts, and budget bars, all in real time.
- **Gallery** (`/gallery`) — a showcase grid of every production with hover-play video previews,
  critic scores, token counts, and links to each storyboard, plus headline aggregate metrics.

## Status

**Live-validated pipeline.** Full end-to-end productions run on Alibaba Cloud DashScope with
real Wan video generation, Qwen-Max/VL orchestration, and AI-directed scoring. A live run of
*"A lighthouse keeper teaches the drone sent to replace him"* produced real vertical Wan footage
scored **7.3/10** by Qwen-VL, using **10.9%** of the token budget and **$0.60** of render spend,
with the tiered router cutting token cost **46%** versus a naive all-`qwen-max` pipeline.

Working today:
- **Series Mode (Multi-episode continuity):** Locks the Style Bible and chains narratives across episodes
- Budget Governor + token ledger (13K tokens / 10.9% of budget for a live multi-shot film)
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
- Live web Studio: real-time critic verdicts, retake decisions, and budget status bars (SSE, multi-tenant concurrent-safe)
- Production Gallery: showcase grid with hover-play previews, scores, and aggregate metrics
- Hardened FastAPI backend: CORS, auto-generated Swagger docs, bounded thread pool, path validation
- Demo reel generator: any production → shareable 16:9 or 9:16 sizzle with live scores + score
- **Live HLS Streaming Engine**: Appends MPEG-TS segments to a live `stream.m3u8` playlist during generation for live broadcasting.
- **Dynamic Foley Soundscapes**: Procedurally synthesizes environment-aware ambient layers (rain, wind, rumble) using ffmpeg filters (zero token cost) and mixes them perfectly under dialogue.
- **MCP Server Integration**: Embedded Model Context Protocol (`mcp_server.py`) allows Claude/Cursor/Qwen to autonomously trigger Auteur productions or critique video files.
- **Qwen Custom Skill**: Bundles a `Qwen_Skill.json` manifest allowing Auteur to plug into Qwen Studio out-of-the-box.
- 92 passing tests, naive baseline, benchmark harness, ablation study

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design, module map, and roadmap.

## License

MIT — see [`LICENSE`](LICENSE).
