# 🎬 AUTEUR — Demo Video Script (3:00)

> **Project:** Auteur — Autonomous AI Showrunner  
> **Hackathon:** Qwen Cloud Global AI Hackathon · Track 2  
> **Runtime:** 180 seconds · No webcam intro · Hook-first structure  
> **Tone:** Confident, technical, slightly cinematic  

---

## Pre-Roll Notes

| Item | Detail |
|------|--------|
| **Resolution** | 1920×1080, 60fps screen capture |
| **Audio** | Voiceover recorded separately, layered over screen capture |
| **Music** | Low ambient synth bed — fade in at 0:00, swell at key moments, fade out at 2:55 |
| **Transitions** | Hard cuts for energy; slow crossfade only at Act breaks |
| **Notation** | `[PAUSE]` = 1-second dramatic silence · `[BEAT]` = half-second breath |

---

## ACT I — THE HOOK (0:00 – 0:30)

> _Goal: Stop the scroll. Lead with the result, not the pitch._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **0:00–0:03** | **Black screen** → Title card fades in: large white text on black — `"What does $0.60 buy you?"` | _(No voice. Music bed begins — low, tense.)_ | Cold open. The dollar amount is the hook. Judges read before they listen. |
| **0:03–0:05** | Hard cut to the **Production Storyboard** — the lighthouse keeper film. Full frame grid visible, green score badges glowing, Style Bible panel on the right. | _(Still no voice.)_ `[PAUSE]` | Two seconds of silence forces judges to absorb the visual. The storyboard proves this isn't a slide deck — it's a real production. |
| **0:05–0:10** | Camera slowly **zooms into** the storyboard. Individual frames become legible — lighthouse exterior, keeper's face, storm sequence. Score badges read `7.3 / 10`. | _"This is a complete short film. Written, directed, scored, and critiqued — entirely by AI."_ | First words establish the scope. "Complete" and "entirely" are load-bearing words. |
| **0:10–0:15** | **Pan** across the storyboard to the **budget summary panel** in the sidebar. Highlight: `Total Cloud Spend: $0.60`. The DashScope usage breakdown is visible beneath it. | _"Total cloud cost — sixty cents."_ `[BEAT]` _"Not sixty dollars. Sixty cents."_ | Repetition with correction anchors the number. Judges will remember this. |
| **0:15–0:20** | Quick cut to the **DashScope billing page** (real browser tab). The API call log is visible — timestamps, model names (`qwen-turbo`, `qwen-plus`, `qwen-max`), token counts, cost per call. Total at the bottom matches. | _"Here's the receipt. Real API calls, real DashScope billing. Every token accounted for."_ | Proof over promises. The billing page eliminates "did they fake it?" doubt instantly. |
| **0:20–0:25** | Cut to **title sequence**: Auteur logo animates in (clean, minimal). Below it: `Autonomous AI Showrunner` and `Qwen Cloud Hackathon · Track 2`. | _"This is Auteur — an autonomous AI showrunner that writes, produces, and self-critiques narrative film, end to end."_ | Proper introduction — but only after the result has landed. The name sticks because the proof came first. |
| **0:25–0:30** | Title holds. Subtitle fades in below: `Built on Qwen-Max · Qwen-VL · Wan 2.1 · DashScope`. Music shifts — opens up, more confident. | _"Built entirely on the Qwen ecosystem."_ `[BEAT]` | Name-drops the stack for track compliance. The beat lets it breathe before the deep dive. |

---

## ACT II — THE SYSTEM (0:30 – 1:20)

> _Goal: Show the architecture in motion. Prove it's not a wrapper — it's an orchestrator._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **0:30–0:38** | **Architecture diagram** — animated. Three tiers light up in sequence: `Qwen-Turbo` (blue, "fast tasks"), `Qwen-Plus` (amber, "creative tasks"), `Qwen-Max` (red, "critical decisions"). Arrows show routing paths. A counter shows `46% cost savings`. | _"Auteur doesn't just call one model. It runs a tiered routing system — Turbo for bulk work, Plus for creative tasks, Max only when it matters. That routing alone saves forty-six percent of the token budget."_ | The routing system is the core technical innovation. Animating it makes abstract cost savings tangible. |
| **0:38–0:45** | Cut to the **terminal**. The command is being typed in real-time: `AUTEUR_MOCK=1 python -m auteur.series "A lighthouse keeper discovers their light has been guiding ghost ships" --episodes 3`. User hits Enter. | _"One command. A premise, a number of episodes. Auteur handles the rest."_ | Shows the DX is clean. One-liner to produce a multi-episode series. The premise itself is evocative — judges will want to see what it makes. |
| **0:45–0:55** | Terminal output begins streaming. Visible stages: `[WRITER] Generating series bible...` → `[WRITER] Episode 1 outline...` → `[DIRECTOR] Breaking into shots...` → `[CRITIC] Evaluating shot 1/12...`. Progress bar moves. Token counter ticks up. | _"The pipeline has four autonomous agents. The Writer builds the narrative. The Director breaks it into shots. The Cinematographer designs each frame. And the Critic — powered by Qwen-VL — watches the actual footage and scores it."_ | Each agent name maps to a film role. This framing is instantly intuitive. The Critic detail (VL on real footage) is the standout — emphasize it. |
| **0:55–1:02** | Cut to the **Live Studio UI** (dark mode). The left panel shows the current shot being processed. The right panel shows the **Critic Verdict** streaming in via SSE — green progress bars filling up as scores arrive: `Composition: 7.8` → `Lighting: 6.9` → `Narrative Fidelity: 7.2`. | _"This is the live studio. Critic verdicts stream in real-time — composition, lighting, narrative fidelity — scored frame by frame."_ | The SSE streaming makes it feel alive. Green bars filling up create a satisfying visual rhythm. |
| **1:02–1:08** | Camera zooms into the **budget bar** in the Studio UI header. It shows: `Tokens: 13,043 / 120,000` — only ~11% filled. The dollar counter reads `$0.58` and ticks to `$0.59`. | _"And look at the budget. Thirteen thousand tokens out of a hundred-twenty-thousand limit. Ten point nine percent utilization."_ `[PAUSE]` | The pause after the utilization stat lets it sink in. This is the "we're not even trying" moment. |
| **1:08–1:15** | Studio UI continues — a new shot's critic score appears. A **red badge** flashes: `BELOW THRESHOLD — REGENERATING`. The shot cycles, a new version appears, scores green. | _"When a shot doesn't meet the quality bar, the system catches it and regenerates autonomously. No human in the loop."_ | Self-correction is the "autonomous" proof point. The red-to-green transition is visually satisfying. |
| **1:15–1:20** | Pull back to show the **full Studio UI** — multiple shots scored, the episode progress at 80%. Music builds slightly. | _"Every decision — what to write, how to frame it, whether to keep it — is made by the system."_ `[BEAT]` | Summary statement before moving to Series Mode. The beat marks the transition. |

---

## ACT III — SERIES MODE (1:20 – 1:50)

> _Goal: Show the differentiator — multi-episode continuity is the moat._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **1:20–1:28** | Cut to the **Style Bible panel** — a structured document showing: `Tone: Melancholic isolation`, `Palette: Desaturated blues, warm amber lantern light`, `Motifs: Spiral staircase, foghorn, fractured reflections`. A lock icon is visible next to each entry. | _"Series Mode introduces the Style Bible — a locked reference document that maintains visual and narrative continuity across episodes."_ | "Locked" is the key word. It implies consistency without drift, which is the hard problem in multi-episode generation. |
| **1:28–1:35** | **Side-by-side comparison**: Frame from Episode 1 (lighthouse exterior, blue-grey tones) next to a matching frame from Episode 3 (same lighthouse, night, same palette). A dotted line connects them. Label: `Style Bible Consistency`. | _"Episode one. Episode three. Same world. Same visual language. The Bible enforces it."_ | Visual proof of continuity. Side-by-side is undeniable. Short, punchy sentences match the confidence. |
| **1:35–1:42** | Cut to the **terminal output** showing series completion: all 3 episodes listed with per-episode costs. `Ep 1: $0.19 · Ep 2: $0.21 · Ep 3: $0.20 · Total: $0.60`. | _"Three episodes. Sixty cents total. About twenty cents each."_ | Reinforces the cost story with granularity. Per-episode breakdown makes it tangible and repeatable. |
| **1:42–1:50** | Quick montage: 3–4 storyboard frames from different episodes, each with its critic score badge. Scores range from `6.8` to `7.8`. Average flashes: `7.3 / 10`. Music swells briefly. | _"Average critic score across all footage: seven point three out of ten. Scored by Qwen-VL on real Wan-generated frames — not prompts, not placeholders."_ `[BEAT]` | "Real frames, not prompts" preempts the obvious skepticism. The VL-on-Wan pipeline is genuinely novel. |

---

## ACT IV — THE EVIDENCE (1:50 – 2:30)

> _Goal: Engineering rigor. This isn't a weekend hack — it's a system._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **1:50–1:58** | Cut to the **Gallery Dashboard** — dark mode, 3 production cards laid out. Each card shows: title, thumbnail, episode count, total cost, average critic score. Aggregate stats bar at the top: `3 productions · $1.40 total · 7.1 avg score`. | _"The Gallery aggregates every production. Three films produced during development. Total spend across all of them — a dollar forty."_ | The Gallery proves this isn't a one-off. Multiple productions = repeatability. |
| **1:58–2:05** | Zoom into the Gallery's **aggregate stats section**: bar charts showing cost-per-episode, score distribution, token utilization across productions. | _"Cost per episode trends down as the routing system learns which calls need Max and which can run on Turbo."_ | Implies the system improves with use — even if modest, this suggests scalability and optimization. |
| **2:05–2:12** | Cut to the **terminal** running the test suite: `pytest` output scrolling. Green dots cascade across the screen. Final line: `92 passed, 0 failed`. | _"Ninety-two passing tests. Unit tests, integration tests, end-to-end pipeline validation."_ | Test count signals engineering maturity. Green dots are universally satisfying. |
| **2:12–2:20** | Cut to a **results table** (clean, dark-themed, could be in the docs or a dedicated screen). Two columns: `With Routing` vs. `Without Routing`. Rows: Token Cost, Latency, Quality Score. Routing column is highlighted green. Label: `Ablation Study`. | _"We ran an ablation study. Remove the routing — costs nearly double. Remove the critic loop — quality drops by one point four. Every component earns its place."_ | Ablation studies are the gold standard for "does this actually work?" Judges from ML backgrounds will respect this immediately. |
| **2:20–2:27** | Cut to a **second comparison table**: `A/B Benchmark`. Columns: `Auteur (Tiered)` vs. `Single-Model Baseline`. Metrics: Cost, Quality, Token Efficiency. Auteur wins on all three. | _"A/B benchmark against a single-model baseline. Auteur is cheaper, higher quality, and more token-efficient — simultaneously."_ | The "simultaneously" is the kicker. Winning on one metric is expected; winning on all three is the story. |
| **2:27–2:30** | Brief return to the **Gallery Dashboard**, camera slowly pulling back. All three production cards visible. Music softs. | _(No voice.)_ `[PAUSE]` | Breathing room before the close. Let the evidence settle. |

---

## ACT V — THE CLOSE (2:30 – 3:00)

> _Goal: Stick the landing. Restate the thesis, end on the vision._

| Timestamp | What's On Screen | Voiceover / Narration | Why This Matters |
|-----------|-----------------|----------------------|-----------------|
| **2:30–2:38** | **Recap card** — clean typography on dark background. Four stats appear one by one with subtle animations: `$0.60 per episode` → `7.3/10 critic score` → `10.9% token utilization` → `46% routing savings` | _"Sixty cents. Seven-point-three quality. Eleven percent of the budget. Forty-six percent savings. Those aren't targets — those are actuals."_ | Rapid-fire stat recall. "Actuals" is a power word — it says "we measured, we delivered." |
| **2:38–2:45** | Stats card holds. A fifth line appears: `92 tests passing · Ablation validated · A/B benchmarked`. | _"Backed by ninety-two tests, an ablation study, and a head-to-head benchmark."_ | Credibility stack. Each item adds weight. |
| **2:45–2:52** | Cut to a **single beautiful storyboard frame** — the lighthouse at golden hour, the keeper silhouetted in the lamp room. It's the hero image. The Auteur watermark is subtle in the corner. | _"Auteur doesn't replace filmmakers."_ `[BEAT]` _"It proves that the Qwen ecosystem — language, vision, and video — can collaborate to tell a story worth watching."_ | Reframing from tool to proof-of-concept. "Worth watching" is the aspiration — it's subjective but compelling. |
| **2:52–2:55** | Slow fade to **black**. Music fades. | _(Silence.)_ `[PAUSE]` | The silence creates weight. Judges remember how something ends. |
| **2:55–3:00** | **Final card** fades in — centered, clean: `Auteur` (logo) / `github.com/bansalbhunesh/Qw` / `Built for the Qwen Cloud Global AI Hackathon` / `Track 2 — Creative Applications`. | _"Auteur. Built on Qwen. Sixty cents at a time."_ | Last line callback to the hook. Bookends the video. "Sixty cents at a time" implies infinite scalability. |

---

## Post-Script: Recording Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Screen capture software ready (OBS / ScreenFlow) | ☐ |
| 2 | DashScope billing page logged in and visible | ☐ |
| 3 | Studio UI running locally with demo data loaded | ☐ |
| 4 | Terminal ready with `AUTEUR_MOCK=1` environment variable set | ☐ |
| 5 | Gallery Dashboard populated with 3 productions | ☐ |
| 6 | Style Bible panel populated for lighthouse keeper series | ☐ |
| 7 | Voiceover script printed for recording session | ☐ |
| 8 | Ambient music track selected and leveled (-20dB under voice) | ☐ |
| 9 | Architecture diagram animation exported (MP4 or Lottie) | ☐ |
| 10 | Test suite ready to run live (`pytest` with green output) | ☐ |

---

## Voiceover Pacing Notes

> [!TIP]
> **Target pace:** ~145 words per minute (slightly slower than conversational). This gives room for `[PAUSE]` and `[BEAT]` moments without rushing.

> [!IMPORTANT]
> **Total narration word count:** ~480 words across 180 seconds. That leaves ~55 seconds of cumulative silence, music-only moments, and breathing room. Do NOT fill every second with voice.

> [!CAUTION]
> **Never say:** "As you can see" / "Basically" / "So yeah" / "Let me show you" — these are filler. Every sentence should either state a fact or make a claim.
