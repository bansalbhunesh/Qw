"""Qwen client — a thin, metered wrapper over a pluggable transport.

Every call is tier-tagged and reported to the Budget Governor so the token ledger is complete,
in both live and mock mode. Agents never touch a transport directly; they go through
`QwenClient` so the Governor sees every token.
"""

from __future__ import annotations

import json
from typing import Any

from .budget import BudgetGovernor
from .config import TIER_MODELS, Tier
from .transport import Transport, make_transport


class QwenClient:
    def __init__(self, governor: BudgetGovernor, transport: Transport | None = None):
        self.governor = governor
        self._t = transport or make_transport()

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
        self.governor.assert_can_spend_tokens(_estimate_tokens(messages))
        content, p_tok, c_tok = self._t.complete(
            stage, model, messages,
            temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
        )
        self.governor.record_llm(stage=stage, model=model, tier=tier,
                                 prompt_tokens=p_tok, completion_tokens=c_tok)
        return content

    def chat_json(self, stage: str, tier: Tier, messages: list[dict[str, Any]], **kw) -> dict:
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
        """A Qwen-VL call. `messages` use the OpenAI multimodal content format (image_url
        entries may be data URIs or OSS URLs). Used by the critic + judge."""
        model = TIER_MODELS[Tier.VISION]
        content, p_tok, c_tok = self._t.complete(
            stage, model, messages, temperature=temperature, max_tokens=None, json_mode=json_mode,
        )
        self.governor.record_llm(stage=stage, model=model, tier=Tier.VISION,
                                 prompt_tokens=p_tok, completion_tokens=c_tok)
        return _loads_lenient(content) if json_mode else content


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Cheap heuristic: ~4 chars/token. Good enough for a pre-flight budget gate."""
    chars = 0
    for m in messages:
        c = m.get("content", "")
        chars += len(c) if isinstance(c, str) else len(str(c))
    return chars // 4 + 256


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
