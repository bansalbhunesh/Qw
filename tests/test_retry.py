"""Retry logic tests."""

import pytest
from auteur.retry import RetryExhausted, with_retry


def test_succeeds_on_first_try():
    assert with_retry(lambda: 42, label="test") == 42


def test_retries_on_transient_failure():
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"
    assert with_retry(flaky, label="test", base_delay=0.01) == "ok"
    assert calls["n"] == 3


def test_gives_up_after_max_retries():
    def always_fail():
        raise ConnectionError("permanent")
    with pytest.raises(RetryExhausted):
        with_retry(always_fail, label="test", max_retries=2, base_delay=0.01)


def test_non_retryable_propagates_immediately():
    calls = {"n": 0}
    def bad_input():
        calls["n"] += 1
        raise ValueError("not retryable")
    with pytest.raises(ValueError):
        with_retry(bad_input, label="test", base_delay=0.01)
    assert calls["n"] == 1  # no retry
