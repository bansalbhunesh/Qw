# 🎬 AUTEUR — Demo Video Script (≤ 3:00)

> **Project:** Auteur — Autonomous AI Showrunner
> **Hackathon:** Qwen Cloud Global AI Hackathon · **Track 2 — AI Showrunner**
> **Runtime:** under 180 seconds · No webcam intro · Hook-first structure
> **Tone:** Confident, technical, slightly cinematic
>
> ⚠️ **Honesty guardrails (read before recording).** Every number here must match what
> the repo actually proves. The live figures ($0.60, 7.3/10, 13,043 tokens, 10.9%) come
> from **one real DashScope + Wan run** stored in `out_live/` — a single production, not a
> live 3-episode series. The **mock** run you show live (`AUTEUR_MOCK=1`) proves the
> pipeline works end-to-end with **no API key**; it does not bill anything. The live model
> stack was the **free tier**: `qwen-max` · `qwen-flash` · `qwen-vl-max` · `wan2.2-t2v-plus`
> (no live TTS). Do **not** claim a live A/B quality win — the live A/B was never run; the
> benchmark validates mechanics and the 7.3 is a measured single-arm result. Say "estimated"
> for the ~46% routing figure. Show the DashScope billing/usage page as the receipt.

---

## Pre-Roll Notes

| Item | Detail |
|------|--------|
| **Resolution** | 1920×1080, 60fps screen capture |
| **Audio** | Voiceover recorded separately, layered over screen capture |
| **Music** | Low ambient synth bed — **self-made or royalty-free only** (no copyrighted music) — fade in at 0:00, fade out by 2:55 |
| **Transitions** | Hard cuts for energy; slow crossfade only at Act breaks |
| **Notation** | `[PAUSE]` = 1-second silence · `[BEAT]` = half-second breath |

---

## ACT I — THE HOOK (0:00 – 0:30)

> _Goal: Stop the scroll. Lead with the result, not the pitch._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **0:00–0:03** | **Black** → title card: `"What does $0.60 buy you?"` | _(No voice. Low, tense music bed begins.)_ | Cold open. The dollar amount is the hook. |
| **0:03–0:08** | Hard cut to the **live-run storyboard** (`out_live/storyboard.html`) — real Wan frames, green score badges reading `7.3 / 10`, the Style Bible panel. | _"This is a real short drama — written, directed, scored, and critiqued by AI."_ `[PAUSE]` | The storyboard is a real committed artifact — not a slide. |
| **0:08–0:14** | Pan to the **budget line** in the live manifest: `13,043 tokens · 10.9% of budget · est. $0.60`. | _"One real cloud run. Thirteen thousand tokens — under eleven percent of the budget. Estimated cost: sixty cents."_ | The measured live numbers, stated as measured. |
| **0:14–0:20** | Cut to the **DashScope usage/billing page** (real browser tab): model names `qwen-max`, `qwen-flash`, `qwen-vl-max`, `wan2.2-t2v-plus`, token counts, timestamps. | _"Here's the receipt — real DashScope calls, every token metered in the ledger."_ | Proof over promises. The billing page kills "did they fake it?" |
| **0:20–0:26** | **Title sequence**: Auteur logo → `Autonomous AI Showrunner` · `Qwen Cloud Hackathon · Track 2`. | _"This is Auteur — an autonomous AI showrunner that writes, produces, and self-critiques short drama, end to end."_ | Proper intro, but only after the proof lands. |
| **0:26–0:30** | Subtitle: `Qwen-Max · Qwen-Flash · Qwen-VL · Wan · DashScope`. | _"Built entirely on the Qwen ecosystem."_ `[BEAT]` | Track-compliance name-drop, accurate to what ran. |

---

## ACT II — THE SYSTEM (0:30 – 1:20)

> _Goal: Show the orchestrator in motion. Prove it's a pipeline, not a wrapper._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **0:30–0:38** | **Architecture diagram**, animated. Three tiers light up: **grunt `qwen-flash`** ("bulk work"), **creative `qwen-max`** ("script & decisions"), **vision `qwen-vl-max`** ("watches the footage"). A counter shows `~46% est. routing savings`. | _"Auteur runs a tiered router — flash for bulk work, max for the creative calls, VL to watch the footage. Routing that grunt work to the cheap tier saves an estimated forty-six percent."_ | The router is the core innovation; "estimated" keeps it honest. |
| **0:38–0:45** | **Terminal**, typed live: `AUTEUR_MOCK=1 python -m auteur.cli "A lighthouse keeper meets a stranger who knows her name" --shots 4`. Enter. | _"One command — and no API key. This runs the entire pipeline in mock mode, so anyone can reproduce it."_ | The zero-key reproduce path is a genuine differentiator — call it out. |
| **0:45–0:55** | Output streams: `[WRITER]…` → `[ART DIRECTOR]…` → `[PROMPT-OPT]…` → `[CINEMATOGRAPHER]…` → `[CRITIC] scoring shot 1…` → `[SOUND]…`. Token counter ticks. | _"A crew of specialist agents: the Writer builds the story, the Art Director locks a Style Bible, the Cinematographer renders each shot on Wan, and the Critic — Qwen-VL — watches the actual frames and scores them."_ | Each agent maps to a film role. The VL-on-real-frames critic is the standout. |
| **0:55–1:03** | **Live Studio** (dark mode). Critic verdict streams via SSE — bars fill: `prompt adherence 7.8` → `character consistency 6.9` → `continuity 7.2`. | _"This is the live Studio. Critic verdicts stream in real time, scored frame by frame."_ | SSE makes it feel alive. |
| **1:03–1:10** | Zoom the **budget meter** in the Studio header ticking as it spends; a **red badge** flashes `BELOW THRESHOLD — RESHOOTING`, the shot re-renders, scores green. | _"When a shot misses the bar, the system spends one budgeted reshoot to fix it — no human in the loop."_ | Self-correction is the "autonomous" proof point; red→green is satisfying. |
| **1:10–1:20** | Cut to the **conditioning ladder** in the ledger: entries reading `r2v` / `i2v` / `t2v` per shot. | _"Character drift is the hard problem. Auteur locks identity with an escalating conditioning ladder — reference-to-video first, degrading gracefully — and records which mode rendered every clip."_ | Shows the pipeline depth rivals don't have, straight from the auditable ledger. |

---

## ACT III — SERIES MODE (1:20 – 1:45)

> _Goal: The differentiator — multi-episode continuity._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **1:20–1:30** | **Style Bible panel** — `Tone`, `Palette`, `Motifs`, each with a lock icon. Then a `python -m auteur.series … --episodes 2` command. | _"Series Mode locks the Style Bible — characters and visual language — then continues the story into the next episode."_ | "Locked" = consistency without drift, the hard multi-episode problem. |
| **1:30–1:45** | **Side-by-side**: a frame from Episode 1 next to a matching frame from Episode 2, same palette. Label: `Style Bible continuity (mock run)`. | _"Episode one, episode two — same world, same look. The Bible enforces it across the whole series."_ | Visual proof of continuity; label it a mock run so nothing is oversold. |

---

## ACT IV — THE EVIDENCE (1:45 – 2:30)

> _Goal: Engineering rigor. Auditable, not asserted._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **1:45–1:55** | **Analytics dashboard** (`/analytics`) — KPIs, tokens-by-model bars, and the **r2v/kf2v/i2v/t2v conditioning-mode distribution**, all from the SQLite store. | _"Every production and every metered call lands in a queryable database — spend, tokens by model, and the conditioning modes it chose. Open the file in any SQLite browser and audit it yourself."_ | Queryable evidence, zero external services — nobody else has this. |
| **1:55–2:03** | **Terminal** running the suite: green dots cascade → `99 passed`. A **green CI badge** on the GitHub repo. | _"Ninety-nine passing tests, green in CI on every push."_ | Test count + CI = engineering maturity, and it's real. |
| **2:03–2:15** | **Ablation table** (`bench/`): each feature toggled off, its contribution shown. Label: `Ablation (mock harness)`. | _"An ablation harness measures what each component contributes — the router, the critic loop, the budget governor — so nothing is decoration."_ | Ablation is the ML gold standard; label it the mock harness to stay exact. |
| **2:15–2:23** | **Ledger view** (`out_live/ledger.json`) scrolling — every call: stage, model, tier, tokens. | _"And it all reconciles to a per-call ledger. The seven-point-three, the sixty cents — measured, row by row, not asserted."_ | The ledger is the moat: auditable claims. |
| **2:23–2:30** | Brief return to the dashboard, slow pull-back. | _(No voice.)_ `[PAUSE]` | Let the evidence settle. |

---

## ACT V — THE CLOSE (2:30 – 3:00)

> _Goal: Restate the thesis; end on the vision._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **2:30–2:40** | **Recap card**, stats appear one by one: `$0.60 (measured)` → `7.3/10 critic score` → `10.9% token use` → `~46% est. routing savings`. | _"Sixty cents. Seven-point-three. Eleven percent of the budget. All measured — here's the ledger that proves it."_ | Rapid recall; "measured" is the power word. |
| **2:40–2:48** | Fifth line: `99 tests · CI green · ablation + benchmark harness · SQLite analytics`. | _"Backed by ninety-nine tests, an ablation and benchmark harness, and a queryable analytics store."_ | Credibility stack — all verifiable. |
| **2:48–2:55** | **Hero storyboard frame** — the lighthouse at golden hour, Auteur watermark. | _"Auteur proves the Qwen ecosystem — language, vision, and video — can collaborate to tell a story worth watching."_ | Tool → proof-of-concept reframe. |
| **2:55–3:00** | Fade to **final card**: `Auteur` · `github.com/bansalbhunesh/Qw` · `Qwen Cloud Global AI Hackathon` · `Track 2 — AI Showrunner`. | _"Auteur. Built on Qwen. Sixty cents at a time."_ | Callback to the hook; correct track name. |

---

## Post-Script: Recording Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Screen capture ready (OBS / Xbox Game Bar `Win+Alt+R`) | ☐ |
| 2 | DashScope **usage/billing page** logged in and visible (the receipt) | ☐ |
| 3 | Studio running locally (`AUTEUR_MOCK=1 python -m auteur.viewer`) with a production loaded | ☐ |
| 4 | `/analytics` dashboard populated (run 1–2 mock productions first) | ☐ |
| 5 | `out_live/storyboard.html` + `ledger.json` open in a tab (the live evidence) | ☐ |
| 6 | Terminal ready with `AUTEUR_MOCK=1` set | ☐ |
| 7 | Voiceover script printed; **no copyrighted music** in the bed | ☐ |
| 8 | Final length checked **< 3:00**; uploaded **public** on YouTube | ☐ |

---

## Voiceover Pacing Notes

> **Target pace:** ~145 words/min. Leaves room for `[PAUSE]`/`[BEAT]`.
>
> **Total narration:** ~470 words across ~180 seconds — do **not** fill every second with voice.
>
> **Never claim:** a live A/B quality win, live TTS, Wan 2.7, or "$0.60" as a billed receipt
> (it's a measured estimate from the ledger). Everything spoken must be provable from the repo.
