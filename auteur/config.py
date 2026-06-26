"""Central configuration: model IDs, endpoints, and budget defaults.

All model calls go through Alibaba Cloud DashScope (international endpoint), which is
OpenAI-compatible — so we drive everything through the OpenAI SDK pointed at DashScope.

API key is read at call time (not import time) so `.env` files loaded via `python-dotenv` or
env vars set after import are picked up.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


# --- DashScope (Alibaba Cloud Model Studio) endpoints -------------------------------------

DASHSCOPE_OPENAI_BASE = os.getenv(
    "DASHSCOPE_OPENAI_BASE",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_NATIVE_BASE = os.getenv(
    "DASHSCOPE_NATIVE_BASE",
    "https://dashscope-intl.aliyuncs.com/api/v1",
)


def _api_key() -> str:
    return os.getenv("DASHSCOPE_API_KEY", "")


class Tier(str, Enum):
    GRUNT = "grunt"
    CREATIVE = "creative"
    VISION = "vision"


TIER_MODELS: dict[Tier, str] = {
    Tier.GRUNT: os.getenv("AUTEUR_MODEL_GRUNT", "qwen-flash"),
    Tier.CREATIVE: os.getenv("AUTEUR_MODEL_CREATIVE", "qwen-max"),
    Tier.VISION: os.getenv("AUTEUR_MODEL_VISION", "qwen-vl-max"),
}

# wan2.2-*-plus is the production-stable Wan family that's available on the DashScope
# International free tier. wan2.7-* exists but its free quota is paywalled ("FreeTierOnly"
# 403); switch to it via AUTEUR_MODEL_WAN_T2V once paid billing is enabled.
WAN_T2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_T2V", "wan2.2-t2v-plus")
WAN_I2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_I2V", "wan2.2-i2v-plus")
TTS_MODEL = os.getenv("AUTEUR_MODEL_TTS", "cosyvoice-v3-plus")


# --- Wan video cost model (for the real-money guardrail) ----------------------------------
# Approximate USD per ~5s Wan clip on DashScope International, keyed by resolution. These are
# conservative estimates used only for a PRE-FLIGHT spend guardrail — actual billing is
# pay-for-success and may differ. Override the per-clip price with AUTEUR_CLIP_USD.
WAN_CLIP_USD: dict[str, float] = {
    "480P": 0.10,
    "720P": 0.20,
    "1080P": 0.40,
}


def clip_price_usd(resolution: str) -> float:
    """Estimated USD cost of one Wan clip at the given resolution (for the spend guardrail)."""
    override = os.getenv("AUTEUR_CLIP_USD")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return WAN_CLIP_USD.get(resolution.upper(), 0.20)


@dataclass
class BudgetConfig:
    max_tokens: int = 120_000
    max_clips: int = 8
    max_retakes: int = 4
    pass_threshold: float = 7.0
    hook_priority_percentile: float = 0.75
    # Hard real-money ceiling on video renders (USD). The Governor stops rendering before a
    # clip would push estimated spend past this, so a test run can never torch your balance.
    max_spend_usd: float = 2.00
    # Estimated USD cost of one Wan clip; set by the Showrunner from the resolution price.
    clip_price_usd: float = 0.0


@dataclass
class ProductionConfig:
    aspect_ratio: str = "9:16"
    target_duration_s: int = 60
    shots: int = 6
    resolution: str = "720P"
    # Visual continuity: seed each shot from the previous shot's final frame (image-to-video)
    # so the character and world stay consistent. Falls back to text-to-video automatically
    # if an i2v render fails, so it never breaks a production.
    consistency: bool = True
    budget: BudgetConfig = field(default_factory=BudgetConfig)


def is_mock() -> bool:
    flag = os.getenv("AUTEUR_MOCK", "").lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return not _api_key()


def require_api_key() -> str:
    key = _api_key()
    if not key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key


