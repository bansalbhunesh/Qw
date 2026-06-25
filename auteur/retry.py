"""Exponential-backoff retry with jitter for all network-facing calls.

Every DashScope (LLM, Wan, TTS) and OSS call goes through this. Rate-limit (429) and transient
server errors (500-503) are retried; client errors and budget violations propagate immediately.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from . import log

_log = log.get("retry")
T = TypeVar("T")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_DEFAULT_MAX_RETRIES = 4
_DEFAULT_BASE_DELAY = 1.5
_DEFAULT_MAX_DELAY = 30.0


class RetryExhausted(RuntimeError):
    """All retries consumed — the underlying error is chained as __cause__."""


def with_retry(
    fn: Callable[[], T],
    *,
    label: str = "call",
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    retryable: Callable[[Exception], bool] | None = None,
) -> T:
    """Call `fn()`, retrying on transient failures with exponential backoff + jitter."""
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_err = exc
            if not _should_retry(exc, retryable):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay *= 0.5 + random.random()  # jitter
            _log.warning(
                "%s attempt %d/%d failed (%s: %s), retrying in %.1fs",
                label, attempt, max_retries, type(exc).__name__, exc, delay,
            )
            time.sleep(delay)
    raise RetryExhausted(f"{label} failed after {max_retries} attempts") from last_err


def _should_retry(exc: Exception, custom: Callable[[Exception], bool] | None) -> bool:
    if custom and custom(exc):
        return True
    # OpenAI SDK rate-limit / server errors
    if hasattr(exc, "status_code") and getattr(exc, "status_code", 0) in _RETRYABLE_STATUS_CODES:
        return True
    # requests.HTTPError
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        if exc.response.status_code in _RETRYABLE_STATUS_CODES:
            return True
    # Generic connection / timeout
    name = type(exc).__name__
    if any(k in name for k in ("Timeout", "Connection", "BrokenPipe")):
        return True
    return False
