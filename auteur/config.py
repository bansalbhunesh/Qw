"""Central configuration: model IDs, endpoints, and budget defaults.

All model calls go through Alibaba Cloud DashScope (international endpoint), which is
OpenAI-compatible — so we drive everything through the OpenAI SDK pointed at DashScope.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


# --- DashScope (Alibaba Cloud Model Studio) endpoints -------------------------------------

# OpenAI-compatible base URL for the international site. Chat + multimodal go here.
DASHSCOPE_OPENAI_BASE = os.getenv(
    "DASHSCOPE_OPENAI_BASE",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)
# Native DashScope REST base — used for async video (Wan) and TTS jobs.
DASHSCOPE_NATIVE_BASE = os.getenv(
    "DASHSCOPE_NATIVE_BASE",
    "https://dashscope-intl.aliyuncs.com/api/v1",
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


class Tier(str, Enum):
    """Model tiers. The Budget Governor routes work to the cheapest tier that can do it."""

    GRUNT = "grunt"      # formatting, cleanup, extraction — cheap + fast
    CREATIVE = "creative"  # the hook, dialogue, final-cut judgement — quality matters
    VISION = "vision"    # Qwen-VL: storyboarding + the critic loop


# Map each tier to a concrete Qwen model. Swap here without touching the agents.
TIER_MODELS: dict[Tier, str] = {
    Tier.GRUNT: os.getenv("AUTEUR_MODEL_GRUNT", "qwen-flash"),
    Tier.CREATIVE: os.getenv("AUTEUR_MODEL_CREATIVE", "qwen-max"),
    Tier.VISION: os.getenv("AUTEUR_MODEL_VISION", "qwen-vl-max"),
}

# Video + audio generation models (native DashScope async jobs).
WAN_T2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_T2V", "wan2.7-t2v")
WAN_I2V_MODEL = os.getenv("AUTEUR_MODEL_WAN_I2V", "wan2.7-i2v")
TTS_MODEL = os.getenv("AUTEUR_MODEL_TTS", "cosyvoice-v2")


@dataclass
class BudgetConfig:
    """The production budget. The Governor enforces these limits."""

    # Hard ceiling on LLM tokens for the whole production (prompt + completion).
    max_tokens: int = 120_000
    # Hard ceiling on the number of video clips rendered (each Wan call costs real money).
    max_clips: int = 8
    # Max reshoots allowed across the whole production.
    max_retakes: int = 4
    # Critic score (0-10) at or above which a clip passes with no reshoot.
    pass_threshold: float = 7.0
    # Shots ranked above this importance percentile get priority on the retake budget.
    hook_priority_percentile: float = 0.75


@dataclass
class ProductionConfig:
    """Per-run knobs for a single short."""

    aspect_ratio: str = "9:16"        # vertical short drama
    target_duration_s: int = 60
    shots: int = 6
    resolution: str = "720P"
    budget: BudgetConfig = field(default_factory=BudgetConfig)


def require_api_key() -> str:
    key = DASHSCOPE_API_KEY
    if not key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key
