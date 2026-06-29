"""Structured production logging.

Every agent gets a named logger. JSON-structured output so the web viewer can stream events
and the ledger tells a coherent story of the production.
"""

from __future__ import annotations

import logging
import sys

_FMT = "[%(asctime)s] %(name)-18s  %(message)s"
_configured = False


def setup(level: int = logging.INFO) -> None:
    """Configure the 'auteur' logger hierarchy (idempotent). Call once at startup."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FMT, datefmt="%H:%M:%S"))
    root = logging.getLogger("auteur")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get(name: str) -> logging.Logger:
    """Return a child logger under the 'auteur' namespace (e.g. 'auteur.writer')."""
    setup()
    return logging.getLogger(f"auteur.{name}")
