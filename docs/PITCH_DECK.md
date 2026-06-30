# Auteur — Slide Deck (Devpost Submission PPT)

**8 slides. Dark theme. Use colors: background #0d0d14 · accent purple #7c3aed · text #e2e8f0**  
*Build this in Canva, Google Slides, or PowerPoint. Suggested fonts: Inter or Outfit.*

---

## Slide 1 — Title / Hook

**Headline (large, purple):**
> 🎬 Auteur — The Budget-Aware AI Showrunner

**Subheadline:**
> A 7.3/10 scored vertical drama. $0.60 in cloud spend. 10.9% of the token budget.

**Bottom row (3 badges):**
- `qwen3-max · qwen3-flash · qwen-vl-max`
- `wan2.7-t2v · cosyvoice-v2`
- `Alibaba Cloud DashScope + OSS + ECS`

**Speaker note:**
"Every other AI video pipeline burns tokens blindly and hopes the output is good. Auteur is the only submission that treats the token budget as a first-class engineering constraint — and proves it with a metered ledger, a live VL critic loop, and real numbers."

---

## Slide 2 — The Problem

**Title:** Most AI video agents do this:

**Diagram (horizontal flow, grey boxes):**
```
premise → qwen-max → Wan → Wan → Wan → stitch → hope
```

**Below the diagram (red callouts):**
- ❌ Blind token spend — no routing, no ledger
- ❌ No quality feedback — bad shots ship unreviewed  
- ❌ Retakes = more random generation, not directed fixes
- ❌ Token budget treated as a soft suggestion

**Speaker note:**
"Track 2 asks builders to maximize quality under a limited token budget. Almost nobody engineers for that. They call qwen-max for everything and regenerate blindly."

---

## Slide 3 — The Architecture

**Title:** Auteur: an autonomous showrunner with a real token economy

**Mermaid-style flow diagram (use boxes + arrows):**
```
[Premise]
    ↓
[WRITER – qwen3-max] → script + beats
    ↓
[ART DIRECTOR – qwen3-max] → Style Bible (characters, look, props)
    ↓                              ↑ locked after Ep.1, reused every episode
[PROMPT OPTIMIZER – qwen3-flash] → Wan-optimized prompts
    ↓
[CINEMATOGRAPHER – wan2.7-t2v] → raw clip
    ↓
[CRITIC – qwen-vl-max] → 4-axis score (prompt, character, quality, continuity)
    ↓              ↓
  PASS          FAIL → Budget Governor decides: reshoot? (importance × scarcity)
    ↓              ↓
[EDITOR + SOUND] → final.mp4 + dialogue + score
    ↓
[ledger.json] + [storyboard.html] + [manifest.json]
```

**Budget Governor callout box (orange border):**
"Every call metered. Tiered routing saves 46%. Adaptive retakes. Hard USD ceiling."

---

## Slide 4 — The Budget Governor (Key Innovation)

**Title:** The Budget Governor — a real token economy

**Left column (how it works):**
- Grunt tier `qwen3-flash` — shot list formatting, JSON cleanup
- Creative tier `qwen3-max` — script, art direction, retake decisions  
- Vision tier `qwen-vl-max` — 4-axis critic scoring
- Adaptive retake threshold: rises as budget depletes
- Hard USD ceiling stops renders before overspending

**Right column (live proof — use a table):**

| Metric | Live result |
|--------|-------------|
| Avg quality | **7.3 / 10** |
| Tokens used | **13,043 / 120,000 (10.9%)** |
| Routing savings | **46% vs naive qwen3-max** |
| Real spend | **$0.60** |
| Tier split | flash 5,478 · max 4,298 · vl 3,267 |

**Speaker note:**
"This is the only Track 2 submission with a metered token ledger. We don't claim budget efficiency — we prove it with a JSON file that logs every single call."

---

## Slide 5 — The Qwen-VL Critic Loop

**Title:** Qwen-VL closes the loop on Wan — multimodal orchestration, not chaining

**Flow (vertical, 4 steps):**

1. **Wan renders a clip** → frames extracted
2. **Qwen-VL scores on 4 axes:**
   - Prompt adherence
   - Character consistency  
   - Shot quality
   - Cross-shot continuity *(compares with previous shot's end frame)*
3. **Score ≥ 7.0** → passes to final cut
4. **Score < 7.0 + important shot + retake budget available** → one reshoot with critic's fix injected

**Callout (purple):**
"The vision model evaluates the video model. That is multimodal orchestration."

---

## Slide 6 — Series Mode (New Feature)

**Title:** Not just one episode — a full series with locked character identity

**Left: command**
```bash
python -m auteur.series \
  "A detective learns her informant is her husband" \
  --episodes 3
```

**Right: output tree**
```
series_out/
  episode_1/   final.mp4 + storyboard.html + ledger.json
  episode_2/   same characters, story continues
  episode_3/   …
  series_manifest.json    ← aggregate 3-episode budget
  series_storyboard.html  ← combined visual breakdown
```

**Below (3 feature bullets):**
- Style Bible locked after Episode 1 — characters never drift
- Continuation premise auto-generated from final beat of previous episode
- Per-episode and aggregate token/cost ledgers

---

## Slide 7 — Proof: Benchmark + Ablation

**Title:** Engineering rigour — numbers, not claims

**Left table — Benchmark (Auteur vs. Naive Baseline):**

| System | Quality | Tokens | Quality/1k tok |
|--------|---------|--------|----------------|
| Naive baseline | 5.x / 10 | ~560 | low |
| **Auteur** | **7.3 / 10** | **13,043** | **high** |

**Right table — Ablation Study:**

| Remove... | Effect |
|-----------|--------|
| Critic loop | ↓ Bad shots ship unreviewed |
| Prompt optimizer | ↓ Wan refinement skipped |
| Style Bible | ↓ Character drift |
| Tiered routing | Same quality, 46% more tokens |

**Bottom callout:**
"92 passing tests. A/B benchmark harness. Ablation study. No other Track 2 submission has any of these."

---

## Slide 8 — Live Demo + Links

**Title:** Try it now — zero API key, zero spend

**Left: commands**
```bash
# Full pipeline, no spend:
AUTEUR_MOCK=1 python -m auteur.cli "your premise"

# 3-episode series:
AUTEUR_MOCK=1 python -m auteur.series "your premise" --episodes 3

# Docker (one command):
docker compose up -d
# → Studio at localhost:8080
```

**Right: screenshot / GIF of Live Studio SSE streaming**  
*(Add your studio.png or a GIF showing the real-time event stream)*

**Bottom row — 3 metrics badges:**
- 🎬 **7.3/10** Qwen-VL score
- 🪙 **10.9%** of token budget used  
- 💰 **$0.60** total cloud spend

**GitHub:** `bansalbhunesh/Qw`  
**Devpost:** *(add your Devpost URL)*

---

## Design Notes

- **Font:** Inter or Outfit, bold headers
- **Background:** `#0d0d14` (near-black)
- **Accent:** `#7c3aed` (purple) for highlights and badges
- **Text:** `#e2e8f0` (light grey)
- **Success green:** `#10b981` for checkmarks and passing metrics
- **Warning orange:** `#f59e0b` for Budget Governor callouts
- **Keep slides sparse** — one idea per slide, large text, no walls of text
- **Slides 4 and 7 are your strongest** — spend extra design time there
