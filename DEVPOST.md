# Auteur — Devpost Submission Copy

This file contains the copy for each Devpost submission field.
Paste each section into the corresponding field on the Devpost project page.

📖 **Full technical deep-dive:** [How I Built an AI Showrunner That Produced a 7.3-Scored Drama for Just $0.60](https://medium.com/@bhuneshbansal20039888/how-i-built-an-ai-showrunner-that-produced-a-7-3-scored-drama-for-just-0-60-0ed3f5b70857)

---

## Project Name
**Auteur — The Budget-Aware AI Showrunner**

---

## Short Description (≤ 200 chars)
An autonomous AI showrunner that turns a one-line premise into a finished vertical short drama — scored 7.3/10 on real Wan footage using only 10.9% of the token budget.

---

## Inspiration

We noticed a pattern across every AI video generation tool: they all treat the token budget as an afterthought. You write a prompt, you generate, you hope. If it's bad, you generate again — burning tokens and money each time. No one was engineering for the constraint that Track 2 explicitly states: *maximize output quality under a limited token budget*.

We thought about how a real film director works. A director never burns film blindly. They plan carefully, review the dailies, spend reshoot budget on the shots that matter most, and cut their losses on the ones that don't. We asked: what would it look like if an AI did the same thing?

That question became Auteur.

---

## What it does

Auteur turns a one-line premise into a complete vertical short drama — script, AI-voiced dialogue, Wan-rendered footage, procedural score, crossfade edits — while treating every token as a conscious decision. It also supports **Series Mode**: after Episode 1 wraps, Auteur locks the Style Bible and reads the final narrative beat to write a seamless Episode 2 continuation. Characters never drift, and the world stays perfectly consistent across a multi-episode arc.

**The result:** A live run produced a 7.3/10-scored vertical short using just 10.9% of the 120,000-token budget, cutting token cost 46% versus a naive all-`qwen-max` approach. Real footage. Real score. Real spend: $0.60.

The system has three core innovations:

**1. The Budget Governor** — a live token economy that meters every LLM, video, and TTS call, routes grunt work to `qwen-flash` and creative decisions to `qwen-max`, allocates retake budget to the most narratively important shots first, and enforces a hard dollar ceiling before a single render happens. The `ledger.json` it produces is a first-class production artifact: auditable proof of every routing decision.

**2. The Qwen-VL Critic Loop** — after each Wan clip renders, Qwen-VL watches it and scores it on four axes: prompt adherence, character consistency, shot quality, and cross-shot visual continuity. A failing take gets one budgeted reshoot with the critic's fix injected. A passing take moves to the cut. The vision model closes the loop on the video model — this is what multimodal orchestration actually means, not just chaining APIs.

**3. Series Mode** — Auteur isn't just a short film generator; it's an episode-native TV showrunner. After generating Episode 1, it permanently locks the Style Bible. For Episode 2, it reads the final narrative beat of Episode 1, writes a seamless continuation, and injects the identical Style Bible. Characters never drift, and the world remains perfectly consistent across a multi-episode run.

The web Studio streams every decision live: script beats being written, Style Bible characters appearing, critic scores ticking in, retake decisions, budget bars depleting — all via Server-Sent Events in real time.

---

## How we built it

**Orchestration:** A Showrunner agent coordinates six specialized sub-agents (Writer, Art Director, Prompt Optimizer, Cinematographer, Editor/Critic, Sound) through a typed event bus. Each agent has a single responsibility; the Showrunner manages the budget and the flow.

**Model stack on Alibaba Cloud DashScope:**
- `qwen-max` — script writing, art direction, retake decisions (creative tier)
- `qwen-flash` — shot-list formatting, prompt cleanup (grunt tier — cheap, fast)
- `qwen-vl-max` — 4-axis critic scoring of real Wan video frames (vision tier)
- `wan2.7-t2v` — text-to-video clip generation
- `wan2.7-i2v` — image-to-video for cross-shot visual continuity
- `cosyvoice-v2` — character dialogue voicing (17 English voice descriptors)

**Backend:** FastAPI with a concurrent-safe multi-tenant SSE event stream (per-production channels via `contextvars`), bounded thread pool for render concurrency, and path-validated production artifact endpoints.

**Frontend:** A dark-mode Studio UI and a Gallery — both built with vanilla HTML/CSS/JS, streaming live production events.

**Evaluation:** A full A/B benchmark harness that runs the same premises through a naive baseline and through Auteur, scored by Qwen-VL as an impartial judge. An ablation study disables each feature in turn to prove its contribution. Both run in deterministic mock mode (no spend) or live.

---

## Try it yourself

Every claim Auteur makes is verifiable. The entire pipeline — budget governor, critic loop, series mode, benchmark, ablation — runs locally in deterministic mock mode with zero API spend. Judges can confirm the architecture end-to-end in under two minutes:

```bash
# Clone and install
git clone https://github.com/YOUR_REPO/auteur.git && cd auteur
pip install -r requirements.txt

# 1. Run a single production (mock mode — no API key needed)
AUTEUR_MOCK=1 python -m auteur.cli "A lighthouse keeper teaches the drone sent to replace him"
# → out/final.mp4 + out/ledger.json + out/storyboard.html

# 2. Run a multi-episode series
AUTEUR_MOCK=1 python -m auteur.series "A detective learns her informant is her husband" --episodes 3
# → series_out/episode_1/ … episode_3/, each with locked Style Bible continuity

# 3. Run the benchmark (Auteur vs. naive baseline)
AUTEUR_MOCK=1 python -m bench.benchmark --premises bench/premises.txt
# → bench/report.md with side-by-side scores

# 4. Run the ablation study
AUTEUR_MOCK=1 python -m bench.ablation --premise "A lighthouse keeper teaches the drone sent to replace him"
# → proves each feature's contribution in isolation

# 5. Run the full test suite (87 tests)
AUTEUR_MOCK=1 python -m pytest -q
```

> **On Windows (PowerShell):** prefix commands with `$env:AUTEUR_MOCK="1";` instead of `AUTEUR_MOCK=1`.

Mock mode swaps two seams — the DashScope LLM client returns structured stubs, and Wan returns a deterministic placeholder clip — without touching any agent logic. The architecture you test is the architecture that runs live.

---

## Challenges we ran into

- **Cross-shot character consistency** — Wan generates each shot independently by default. We solved this with two strategies: the Style Bible (character descriptions injected into every prompt via the Art Director) and image-to-video continuity chaining (the final frame of shot N seeds shot N+1 via OSS upload). Qwen-VL then scores continuity across adjacent frames to catch drift before it ships.

- **Adaptive retake decisions** — A fixed quality threshold is naive. As the retake budget depletes, the bar for "is this shot worth reshooting?" should rise. We implemented an adaptive scarcity function: `adaptive_threshold = hook_priority_percentile + 0.1 × scarcity_ratio`. The system becomes more selective under budget pressure — exactly like a real director.

- **Windows-safe ffmpeg assembly** — FFmpeg's complex concat filter behaves differently on Windows. We implemented a concat-filter fallback path and tested the full assembly pipeline on Windows, Linux, and inside Docker.

- **CosyVoice voice attribution** — Assigning the right voice to each line of dialogue required three fallback strategies: explicit speaker tag parsing (`NAME: line`), character name mention scanning, and shot-index parity. A TTS failure never discards a rendered clip.

---

## Accomplishments that we're proud of

- **7.3/10** Qwen-VL score on real Wan footage, using **10.9%** of the token budget
- **46% token cost reduction** via tiered model routing, proven by the `ledger.json`
- A **benchmark harness** that scores Auteur vs. a naive baseline using Qwen-VL as an impartial judge — in a field where ~95% of hackathon submissions have zero evaluation
- An **ablation study** that disables each architectural feature in turn to prove its contribution — not a grab-bag of features, an engineered system
- **Series Mode** that locks the Style Bible after Episode 1 and maintains character and world consistency across a multi-episode arc
- **Live HLS Streaming Engine** and **Dynamic Foley Soundscapes** generated procedurally via ffmpeg to create environment-aware audio layers under the dialogue
- **Embedded MCP Server integration** providing native Qwen Studio/Cursor autonomous control with a ready-to-use `Qwen_Skill.json`
- **87 passing tests**, covering every agent, the budget governor, the event bus, the storyboard export, and the web API
- A production that is **truly resilient**: voice failures don't discard clips, partial-shot recovery, Windows-safe assembly, quota-exhaustion detection with clear guidance

### Audit Trail

We believe the strongest proof of an engineering claim is an open ledger. Every production Auteur runs — mock or live — emits a `ledger.json`: a line-by-line record of every API call, the model tier it was routed to, the tokens consumed, the dollar cost, and the agent that requested it.

We invite judges to inspect `out/ledger.json` (or `out_live/ledger.json` for the live run) directly. The 46% cost reduction, the tiered routing decisions, the retake budget allocation — it's all there, row by row. No summary statistics without the raw data to back them up.

---

## What we learned

- The "quality under a budget" constraint is genuinely hard — and genuinely worth engineering for. Most teams treat it as a soft guideline; treating it as a hard constraint with metered proof changes the entire architecture.
- Qwen-VL is a surprisingly capable critic. The 4-axis scoring rubric (prompt adherence, character consistency, shot quality, cross-shot continuity) maps well to how humans evaluate short drama.
- `qwen-flash` for grunt work is not a compromise — it's a feature. The prompt formatting and shot-list cleanup that flash handles are latency-sensitive and don't need creative reasoning. Routing them to flash saves tokens *and* speeds up the pipeline.

---

## What's next for Auteur

- **Longer-form content** — the beat-sheet architecture scales; 3-act structure is the next step
- **Style transfer** — using Qwen-VL to extract a visual style from a reference video and inject it into the Style Bible
- **Interactive editing** — let users intervene between shots (change a beat, re-score a clip) via the Studio UI
- **Multi-language voicing** — CosyVoice supports multiple languages; the dialogue attribution system is already voice-agnostic

---

## Built With

`python` · `qwen-max` · `qwen-flash` · `qwen-vl-max` · `wan2.7-t2v` · `cosyvoice-v2` · `alibaba-cloud` · `dashscope` · `alibaba-oss` · `fastapi` · `ffmpeg` · `uvicorn` · `pillow` · `pytest` · `docker`

---

📖 **Read the full build story:** [How I Built an AI Showrunner That Produced a 7.3-Scored Drama for Just $0.60 — Medium](https://medium.com/@bhuneshbansal20039888/how-i-built-an-ai-showrunner-that-produced-a-7-3-scored-drama-for-just-0-60-0ed3f5b70857)
