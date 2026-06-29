"""The Budget Governor — Auteur's token economy.

This is the differentiator. Every LLM/video/TTS call is metered here. The Governor:
  * records spend in a per-production ledger,
  * refuses work that would blow the budget,
  * decides whether a failing clip is *worth* a reshoot given remaining budget and the
    shot's narrative importance.

The ledger it produces (`ledger.json`) is a first-class deliverable: it's how we prove the
"quality under a limited token budget" claim in the benchmark.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import BudgetConfig, Tier


@dataclass
class LedgerEntry:
    """One row in the production ledger — a single metered API call."""

    ts: float                 # Unix timestamp of the call
    stage: str                # which agent ("writer", "critic", ...)
    kind: str                 # "llm" | "video" | "tts"
    model: str                # concrete model ID (e.g. "qwen3-flash")
    tier: str | None          # cost tier ("grunt"/"creative"/"vision"), None for non-LLM
    prompt_tokens: int = 0    # input tokens consumed
    completion_tokens: int = 0  # output tokens consumed
    clips: int = 0            # number of video clips rendered (for kind="video")
    note: str = ""            # free-text annotation (prompt snippet, failure reason, etc.)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class BudgetState:
    """Mutable counters tracking resource consumption during a production."""

    tokens_used: int = 0     # total LLM tokens consumed (prompt + completion)
    clips_used: int = 0      # total video clips rendered (originals + retakes)
    retakes_used: int = 0    # number of reshoot attempts consumed


class BudgetExceeded(RuntimeError):
    """Raised when an operation would exceed a hard budget ceiling."""


class BudgetGovernor:
    """Central resource controller — meters every API call and enforces hard ceilings.

    The Governor is the single source of truth for resource consumption. Every LLM,
    video, and TTS call flows through its ``record_*`` methods, and every resource
    allocation check flows through its ``can_*`` / ``assert_*`` gates. The resulting
    ledger (``ledger.json``) is a first-class deliverable that proves budget compliance.
    """

    def __init__(self, budget: BudgetConfig, ledger_path: str | Path | None = None):
        self.budget = budget
        self.state = BudgetState()
        self.entries: list[LedgerEntry] = []
        self.ledger_path = Path(ledger_path) if ledger_path else None

    # --- metering --------------------------------------------------------------------

    def record_llm(
        self, stage: str, model: str, tier: Tier, prompt_tokens: int, completion_tokens: int,
        note: str = "",
    ) -> None:
        """Record an LLM call's token consumption in the ledger."""
        self.state.tokens_used += prompt_tokens + completion_tokens
        self.entries.append(
            LedgerEntry(
                ts=time.time(), stage=stage, kind="llm", model=model, tier=tier.value,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, note=note,
            )
        )

    def record_video(self, stage: str, model: str, clips: int = 1, note: str = "") -> None:
        """Record a video render in the ledger and increment the clip counter."""
        self.state.clips_used += clips
        self.entries.append(
            LedgerEntry(ts=time.time(), stage=stage, kind="video", model=model, tier=None,
                        clips=clips, note=note)
        )

    def record_tts(self, stage: str, model: str, note: str = "") -> None:
        """Record a text-to-speech synthesis call in the ledger."""
        self.entries.append(
            LedgerEntry(ts=time.time(), stage=stage, kind="tts", model=model, tier=None, note=note)
        )

    # --- gates -----------------------------------------------------------------------

    def assert_can_spend_tokens(self, estimated: int) -> None:
        if self.state.tokens_used + estimated > self.budget.max_tokens:
            raise BudgetExceeded(
                f"token budget exhausted: {self.state.tokens_used}/{self.budget.max_tokens}"
            )

    def can_render_clip(self) -> bool:
        """True if another clip is allowed by BOTH the count cap and the dollar cap."""
        if self.state.clips_used >= self.budget.max_clips:
            return False
        return not self._would_exceed_cost()

    def _would_exceed_cost(self) -> bool:
        """Whether rendering one more clip would push estimated spend past the dollar cap."""
        price = self.budget.clip_price_usd
        if price <= 0:
            return False  # pricing not configured (e.g. mock) — count cap governs
        projected = (self.state.clips_used + 1) * price
        return projected > self.budget.max_spend_usd

    @property
    def estimated_cost_usd(self) -> float:
        return round(self.state.clips_used * self.budget.clip_price_usd, 4)

    def clip_cap(self) -> int:
        """The effective clip ceiling — the tighter of the count cap and the dollar cap."""
        price = self.budget.clip_price_usd
        if price <= 0:
            return self.budget.max_clips
        by_cost = int(self.budget.max_spend_usd // price)
        return min(self.budget.max_clips, by_cost)

    def should_retake(self, critic_score: float, shot_importance: float) -> bool:
        """Decide whether a failing clip earns a reshoot.

        A reshoot happens only if: the shot failed the bar, we have retake budget left, we
        have clip budget left, and the shot is important enough to justify spending a
        scarce retake on it (the hook beats a cutaway).

        Adaptive threshold: as budget runs low, the bar for importance rises. This ensures
        the system becomes more selective as resources dwindle — a production-grade behavior
        that static thresholds can't match.
        """
        # Gate 1: the shot already passed the quality bar — no reshoot needed.
        if critic_score >= self.budget.pass_threshold:
            return False
        # Gate 2: hard retake count ceiling — no budget left for any reshoot.
        if self.state.retakes_used >= self.budget.max_retakes:
            return False
        # Gate 3: clip budget or dollar cap exhausted — can't render even if wanted.
        if not self.can_render_clip():
            return False

        # --- Adaptive scarcity-based importance threshold ---
        # As retakes are consumed, `scarcity` rises from 0.0 (full budget) to 1.0
        # (last retake). This linearly raises the importance bar a shot must clear
        # to earn a reshoot, ensuring late-budget retakes are reserved for the most
        # narratively critical shots (hooks > cutaways).
        remaining_retakes = self.budget.max_retakes - self.state.retakes_used
        total_retakes = self.budget.max_retakes
        # scarcity ∈ [0, 1]: 0 = all retakes available, 1 = last retake remaining
        scarcity = 1.0 - (remaining_retakes / max(1, total_retakes))
        # Raise the base threshold (default 0.75) by up to +0.10 as budget depletes.
        # At full budget: threshold = 0.75 (generous). At last retake: 0.85 (selective).
        adaptive_threshold = self.budget.hook_priority_percentile + 0.1 * scarcity
        # Only reshoot if the shot's narrative importance clears the adaptive bar.
        return shot_importance >= adaptive_threshold

    def register_retake(self) -> None:
        self.state.retakes_used += 1

    # --- reporting -------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a serializable snapshot of budget state for manifests and the web viewer."""
        return {
            "tokens_used": self.state.tokens_used,
            "token_budget": self.budget.max_tokens,
            "clips_used": self.state.clips_used,
            "clip_budget": self.budget.max_clips,
            "retakes_used": self.state.retakes_used,
            "retake_budget": self.budget.max_retakes,
            "estimated_cost_usd": self.estimated_cost_usd,
            "max_spend_usd": self.budget.max_spend_usd,
            "tokens_by_stage": self._tokens_by_stage(),
            "tokens_by_tier": self._tokens_by_tier(),
        }

    def _tokens_by_stage(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            if e.kind == "llm":
                out[e.stage] = out.get(e.stage, 0) + e.total_tokens
        return out

    def _tokens_by_tier(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            if e.kind == "llm" and e.tier:
                out[e.tier] = out.get(e.tier, 0) + e.total_tokens
        return out

    def flush(self) -> None:
        """Write the ledger to disk if a path was configured."""
        if not self.ledger_path:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": self.summary(),
            "entries": [asdict(e) for e in self.entries],
        }
        self.ledger_path.write_text(json.dumps(payload, indent=2))
