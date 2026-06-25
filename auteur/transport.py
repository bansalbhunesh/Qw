"""Transport layer — where LLM calls actually go.

`QwenClient` (in llm.py) handles metering, routing, and JSON parsing; it delegates the actual
completion to a Transport. This indirection lets the entire pipeline run in two modes:

  * OpenAITransport — real Qwen / Qwen-VL via the OpenAI-compatible DashScope endpoint.
  * MockTransport   — deterministic, offline fakes that return stage-appropriate structured
                      content, so orchestration, the budget ledger, retake logic, and the
                      benchmark are all testable without a key or spend.

The mock returns are intentionally varied (some clips fail the critic) so the retake economics
are genuinely exercised, not bypassed.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Protocol

from .config import DASHSCOPE_OPENAI_BASE, require_api_key


class Transport(Protocol):
    def complete(
        self, stage: str, model: str, messages: list[dict[str, Any]],
        *, temperature: float, max_tokens: int | None, json_mode: bool,
    ) -> tuple[str, int, int]:
        """Return (content, prompt_tokens, completion_tokens)."""
        ...


# --- live --------------------------------------------------------------------------------

class OpenAITransport:
    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=require_api_key(), base_url=DASHSCOPE_OPENAI_BASE)

    def complete(self, stage, model, messages, *, temperature, max_tokens, json_mode):
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        usage = resp.usage
        return (
            resp.choices[0].message.content or "",
            getattr(usage, "prompt_tokens", 0),
            getattr(usage, "completion_tokens", 0),
        )


# --- mock --------------------------------------------------------------------------------

def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


def _text_of(messages: list[dict[str, Any]]) -> str:
    """Flatten message content (handles multimodal list content) to plain text."""
    out: list[str] = []
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            out.extend(part.get("text", "") for part in c if part.get("type") == "text")
    return "\n".join(out)


class MockTransport:
    """Deterministic offline fakes. Same input → same output, so tests are stable."""

    def complete(self, stage, model, messages, *, temperature, max_tokens, json_mode):
        text = _text_of(messages)
        content = self._dispatch(stage, text)
        # Token counts: estimate prompt, fabricate a plausible completion size.
        prompt_tokens = max(1, len(text) // 4)
        completion_tokens = max(1, len(content) // 4)
        return content, prompt_tokens, completion_tokens

    def _dispatch(self, stage: str, text: str) -> str:
        low = text.lower()
        if "beat sheet" in low or '"beats"' in low or "-beat micro-drama" in low:
            return self._beats(text)
        if '"shots"' in low or "for each beat, write one shot" in low:
            return self._shots(text)
        if "art director" in low or '"look"' in low:
            return self._bible(text)
        if "rubric" in stage or "judge" in low or "narrative_coherence" in low:
            return self._judge(text)
        if stage == "critic" or "score these frames" in low:
            return self._critique(text)
        return json.dumps({"ok": True})

    # individual stage fakes -------------------------------------------------------------

    def _beats(self, text: str) -> str:
        m = re.search(r"(\d+)-beat", text)
        n = int(m.group(1)) if m else 6
        labels = ["Hook", "Setup", "Turn", "Crisis", "Button", "Tag", "Coda", "Echo"]
        beats = []
        for i in range(n):
            importance = 1.0 if i == 0 else round(0.4 + 0.5 * (1 - i / max(1, n)), 2)
            beats.append({
                "label": labels[i % len(labels)],
                "summary": f"Beat {i + 1}: a turn in the story that raises the stakes.",
                "importance": importance,
            })
        return json.dumps({"logline": "A quiet moment cracks open a hidden truth.", "beats": beats})

    def _shots(self, text: str) -> str:
        n = len(re.findall(r"(?m)^\s*\d+\.", text)) or 6
        shots = []
        for i in range(n):
            shots.append({
                "beat_index": i,
                "description": f"Shot {i + 1}: medium close-up, slow push-in, soft practical light.",
                "dialogue": "" if i % 2 else "I never thought you'd come back.",
                "video_prompt": f"cinematic vertical shot {i + 1}, a person in a dim room, "
                                f"emotional, shallow depth of field, 35mm",
            })
        return json.dumps({"shots": shots})

    def _bible(self, text: str) -> str:
        return json.dumps({
            "look": "muted teal grade, 35mm, shallow depth of field, soft practical lighting",
            "characters": [
                {"name": "Mara", "description": "late 30s, short dark hair, navy scrubs, tired eyes",
                 "voice": "warm"},
            ],
        })

    def _critique(self, text: str) -> str:
        # Deterministically vary scores so some shots fail and trigger the retake economics.
        s = _seed("critique", text[:200]) % 100
        overall = 5.0 + (s % 50) / 10.0  # 5.0 .. 9.9
        fix = "" if overall >= 7.0 else "tighten framing and increase contrast on the subject"
        return json.dumps({
            "prompt_adherence": round(min(10.0, overall + 0.3), 1),
            "character_consistency": round(max(0.0, overall - 0.4), 1),
            "shot_quality": round(overall, 1),
            "overall": round(overall, 1),
            "fix": fix,
        })

    def _judge(self, text: str) -> str:
        s = _seed("judge", text[:200]) % 100
        base = 6.5 + (s % 30) / 10.0
        return json.dumps({
            "narrative_coherence": round(base, 1),
            "visual_quality": round(min(10.0, base + 0.4), 1),
            "character_consistency": round(max(0.0, base - 0.3), 1),
            "emotional_impact": round(base, 1),
            "overall": round(base, 1),
            "notes": "Mock judgement — deterministic placeholder until live scoring.",
        })


def make_transport() -> Transport:
    from .config import is_mock

    return MockTransport() if is_mock() else OpenAITransport()
