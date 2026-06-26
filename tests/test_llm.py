"""LLM client tests — JSON parsing, repair, vision fallback."""

import os
import pytest

os.environ["AUTEUR_MOCK"] = "1"

from auteur.budget import BudgetGovernor
from auteur.config import BudgetConfig, Tier
from auteur.llm import QwenClient, _loads_lenient


def _client():
    return QwenClient(BudgetGovernor(BudgetConfig()))


class TestLoadsLenient:
    def test_plain_json(self):
        assert _loads_lenient('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert _loads_lenient('```json\n{"a": 1}\n```') == {"a": 1}

    def test_prose_then_json(self):
        assert _loads_lenient('Here is the result: {"a": 1}') == {"a": 1}

    def test_trailing_comma(self):
        assert _loads_lenient('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            _loads_lenient("no json here at all")


def test_chat_json_returns_dict():
    client = _client()
    result = client.chat_json("test", Tier.CREATIVE, [
        {"role": "system", "content": "Return JSON."},
        {"role": "user", "content": "Write a 3-beat micro-drama beat sheet."},
    ])
    assert isinstance(result, dict)
    assert "beats" in result or "logline" in result


def test_vision_returns_dict():
    client = _client()
    result = client.vision("test", [
        {"role": "system", "content": "Score these frames. Return JSON."},
        {"role": "user", "content": [
            {"type": "text", "text": "Score these frames from the rendered clip."},
        ]},
    ])
    assert isinstance(result, dict)


def test_token_estimation_with_images():
    client = _client()
    # Should not crash on multimodal content
    client.chat("test", Tier.VISION, [
        {"role": "user", "content": [
            {"type": "text", "text": "Hello"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]},
    ])
    assert client.governor.state.tokens_used > 0


class TestLoadsLenientEdgeCases:
    def test_nested_json(self):
        raw = '{"a": {"b": [1, 2, 3]}, "c": "d"}'
        assert _loads_lenient(raw) == {"a": {"b": [1, 2, 3]}, "c": "d"}

    def test_json_with_whitespace(self):
        raw = '  \n  {"a": 1}  \n  '
        assert _loads_lenient(raw) == {"a": 1}

    def test_markdown_json_block(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _loads_lenient(raw) == {"key": "value"}

    def test_json_embedded_in_explanation(self):
        raw = 'Here is your answer:\n{"result": true}\nHope this helps!'
        assert _loads_lenient(raw) == {"result": True}


def test_chat_json_metering():
    """All chat_json calls should be metered by the Governor."""
    client = _client()
    client.chat_json("test_stage", Tier.GRUNT, [
        {"role": "user", "content": "Write a 3-beat micro-drama beat sheet."},
    ])
    summary = client.governor.summary()
    assert summary["tokens_by_stage"].get("test_stage", 0) > 0
