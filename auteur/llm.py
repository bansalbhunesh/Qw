"""Qwen client — a metered, validated wrapper over a pluggable transport.

Every call is tier-tagged and reported to the Budget Governor. Agents go through `QwenClient`
so the Governor sees every token. JSON responses are validated and recovered on parse failure.
"""

from __future__ import annotations

import json
from typing import Any

from . import log
from .budget import BudgetGovernor
from .config import TIER_MODELS, Tier
from .transport import Transport, make_transport

_log = log.get("llm")

_JSON_REPAIR_ATTEMPTS = 2


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
        model = TIER_MODELS[tier]
        self.governor.assert_can_spend_tokens(_estimate_tokens(messages))
        content, p_tok, c_tok = self._t.complete(
            stage, model, messages,
            temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
        )
        self.governor.record_llm(stage=stage, model=model, tier=tier,
                                 prompt_tokens=p_tok, completion_tokens=c_tok)
        return content

    def chat_json(
        self,
        stage: str,
        tier: Tier,
        messages: list[dict[str, Any]],
        **kw,
    ) -> dict:
        """Chat that must return valid JSON. Retries once with a repair prompt on parse failure."""
        raw = self.chat(stage, tier, messages, json_mode=True, **kw)
        try:
            return _loads_lenient(raw)
        except (json.JSONDecodeError, ValueError) as first_err:
            _log.warning("[%s] JSON parse failed, requesting repair: %s", stage, first_err)
            repair_msgs = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Your previous response was not valid JSON. Return ONLY the corrected "
                    "JSON object with no surrounding text or markdown fences."
                )},
            ]
            raw2 = self.chat(stage, tier, repair_msgs, json_mode=True, **kw)
            return _loads_lenient(raw2)

    def vision(
        self,
        stage: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> dict | str:
        """A Qwen-VL call with multimodal content (image_url entries as data URIs or URLs)."""
        model = TIER_MODELS[Tier.VISION]
        self.governor.assert_can_spend_tokens(_estimate_tokens(messages))
        content, p_tok, c_tok = self._t.complete(
            stage, model, messages, temperature=temperature, max_tokens=None, json_mode=json_mode,
        )
        self.governor.record_llm(stage=stage, model=model, tier=Tier.VISION,
                                 prompt_tokens=p_tok, completion_tokens=c_tok)
        if not json_mode:
            return content
        try:
            return _loads_lenient(content)
        except (json.JSONDecodeError, ValueError):
            _log.warning("[%s] vision JSON parse failed, returning defaults", stage)
            return {"overall": 5.0, "fix": ""}


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    chars = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            chars += len(c)
        elif isinstance(c, list):
            for part in c:
                if part.get("type") == "text":
                    chars += len(part.get("text", ""))
                elif part.get("type") == "image_url":
                    chars += 1500  # vision tokens for an image
        else:
            chars += len(str(c))
    return chars // 4 + 256


def _loads_lenient(raw: str) -> dict:
    """Parse JSON tolerating markdown fences, leading prose, and trailing commas."""
    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 3:
            raw = parts[1]
        else:
            raw = parts[-1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
        raw = raw.strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Find the outermost JSON object
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    # Try removing trailing commas before closing braces/brackets
                    import re
                    cleaned = re.sub(r",\s*([}\]])", r"\1", raw[start : i + 1])
                    return json.loads(cleaned)
    raise ValueError(f"no valid JSON object found in response ({len(raw)} chars)")
