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
    # qwen3-flash / qwen3-max are the latest generation (June 2026). The env-var overrides
    # let you pin to older models if your DashScope account lacks access.
    Tier.GRUNT: os.getenv("AUTEUR_MODEL_GRUNT", "qwen3-flash"),
    Tier.CREATIVE: os.getenv("AUTEUR_MODEL_CREATIVE", "qwen3-max"),
    Tier.VISION: os.getenv("AUTEUR_MODEL_VISION", "qwen-vl-max"),
}

# Wan 2.7 is the latest stable video generation model on DashScope International.
# wan2.2-*-plus is kept as a fallback if your account only has the free tier.
# Switch via AUTEUR_MODEL_WAN_T2V env var.
WAN_T2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_T2V", "wan2.7-t2v")
WAN_I2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_I2V", "wan2.7-i2v")
TTS_MODEL = os.getenv("AUTEUR_MODEL_TTS", "cosyvoice-v2")


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


# Wan accepts an explicit pixel `size` ("width*height") that fixes BOTH resolution and aspect
# ratio. "resolution" alone defaults to 16:9 landscape, which is wrong for a vertical short
# drama — so we always send an explicit vertical size for 9:16.
_WAN_SIZES: dict[tuple[str, str], str] = {
    ("480P", "9:16"): "480*832",
    ("720P", "9:16"): "720*1280",
    ("1080P", "9:16"): "1080*1920",
    ("480P", "16:9"): "832*480",
    ("720P", "16:9"): "1280*720",
    ("1080P", "16:9"): "1920*1080",
    ("480P", "1:1"): "624*624",
    ("720P", "1:1"): "960*960",
    ("1080P", "1:1"): "1440*1440",
}


def wan_size(resolution: str, aspect_ratio: str = "9:16") -> str:
    """Map a resolution + aspect ratio to a Wan `size` string ("width*height")."""
    override = os.getenv("AUTEUR_WAN_SIZE")
    if override:
        return override
    return _WAN_SIZES.get((resolution.upper(), aspect_ratio), "720*1280")


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
    # Quality gate: drop shots scoring below this threshold from the final cut (0 = keep all).
    quality_gate: float = 0.0
    # Dynamic resolution: hero shots (importance >= threshold) render at hero_resolution,
    # others at base_resolution. Saves real money while keeping hero shots crisp.
    dynamic_resolution: bool = False
    hero_resolution: str = "1080P"
    base_resolution: str = "480P"
    hero_importance_threshold: float = 0.8
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


