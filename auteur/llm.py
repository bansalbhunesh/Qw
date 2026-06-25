"""Qwen client — a thin, metered wrapper over the OpenAI-compatible DashScope endpoint.

Every call is tier-tagged and reported to the Budget Governor so the token ledger is
complete. Agents never instantiate clients directly; they go through `QwenClient` so the
Governor sees every token.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .budget import BudgetGovernor
from .config import DASHSCOPE_OPENAI_BASE, TIER_MODELS, Tier, require_api_key


class QwenClient:
    def __init__(self, governor: BudgetGovernor):
        self.governor = governor
        self._client = OpenAI(api_key=require_api_key(), base_url=DASHSCOPE_OPENAI_BASE)

    def chat(
        self,
        stage: str,
        tier: Tier,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.8,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """A budgeted chat completion. Returns the assistant message content."""
        model = TIER_MODELS[tier]
        # Rough pre-flight estimate so we fail before paying, not after.
        self.governor.assert_can_spend_tokens(_estimate_tokens(messages))

        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self._client.chat.completions.create(**kwargs)
        usage = resp.usage
        self.governor.record_llm(
            stage=stage, model=model, tier=tier,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
        )
        return resp.choices[0].message.content or ""

    def chat_json(self, stage: str, tier: Tier, messages: list[dict[str, Any]], **kw) -> dict:
        """Chat that must return a JSON object. Parses and returns the dict."""
        raw = self.chat(stage, tier, messages, json_mode=True, **kw)
        return _loads_lenient(raw)

    def vision(
        self,
        stage: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> dict | str:
        """A Qwen-VL call. `messages` use the OpenAI multimodal content format
        (image_url entries may be data URIs or OSS URLs). Used by the critic loop."""
        model = TIER_MODELS[Tier.VISION]
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        usage = resp.usage
        self.governor.record_llm(
            stage=stage, model=model, tier=Tier.VISION,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
        )
        content = resp.choices[0].message.content or ""
        return _loads_lenient(content) if json_mode else content


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Cheap heuristic: ~4 chars/token. Good enough for a pre-flight budget gate."""
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    return chars // 4 + 256  # headroom for the completion


def _loads_lenient(raw: str) -> dict:
    """Parse JSON that may be wrapped in markdown fences or have leading prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start : end + 1])
        raise
