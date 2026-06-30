"""Production event bus — typed events emitted during a run for the web viewer to stream.

Agents emit events (beat written, shot rendered, critic verdict, etc.) into a thread-safe
queue. The web viewer SSE endpoint consumes them in real time. When no viewer is attached the
events are simply discarded, so the pipeline has zero overhead.
"""

from __future__ import annotations

import contextvars
import json
import queue
import time
from dataclasses import dataclass, field
from typing import Any

active_production = contextvars.ContextVar("active_production", default=None)

@dataclass
class Event:
    kind: str
    stage: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = {"kind": self.kind, "stage": self.stage, "ts": self.ts, **self.data}
        return f"data: {json.dumps(payload)}\n\n"


class EventBus:
    """Thread-safe pub-sub for production events."""

    def __init__(self):
        self._subscribers: dict[str, list[queue.Queue[Event | None]]] = {}

    def subscribe(self, prod_id: str) -> queue.Queue[Event | None]:
        q: queue.Queue[Event | None] = queue.Queue(maxsize=256)
        self._subscribers.setdefault(prod_id, []).append(q)
        return q

    def unsubscribe(self, prod_id: str, q: queue.Queue) -> None:
        if prod_id in self._subscribers:
            self._subscribers[prod_id] = [s for s in self._subscribers[prod_id] if s is not q]
            if not self._subscribers[prod_id]:
                del self._subscribers[prod_id]

    def emit(self, kind: str, stage: str, **data) -> None:
        prod_id = active_production.get()
        ev = Event(kind=kind, stage=stage, data=data)
        subs = self._subscribers.get(prod_id, []) if prod_id else []
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass  # slow consumer — drop the event

    def close(self, prod_id: str) -> None:
        subs = self._subscribers.pop(prod_id, [])
        for q in subs:
            try:
                q.put_nowait(None)
            except queue.Full:
                pass


# Global singleton — agents import this and call `bus.emit(...)`.
bus = EventBus()
