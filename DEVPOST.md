# Auteur — Devpost Submission Copy

This file contains the copy for each Devpost submission field.
Paste each section into the corresponding field on the Devpost project page.

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

Auteur turns a one-line premise into a complete vertical short drama — script, AI-voiced dialogue, Wan-rendered footage, procedural score, crossfade edits — while treating every token as a conscious decision.

**The result:** A live run produced a 7.3/10-scored vertical short using just 10.9% of the 120,000-token budget, cutting token cost 46% versus a naive all-`qwen-max` approach. Real footage. Real score. Real spend: $0.60.

The system has two core innovations:

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
- **85 passing tests**, covering every agent, the budget governor, the event bus, the storyboard export, and the web API
- A production that is **truly resilient**: voice failures don't discard clips, partial-shot recovery, Windows-safe assembly, quota-exhaustion detection with clear guidance

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
