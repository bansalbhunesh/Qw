"""Production event bus — typed events emitted during a run for the web viewer to stream.

Agents emit events (beat written, shot rendered, critic verdict, etc.) into a thread-safe
queue. The web viewer SSE endpoint consumes them in real time. When no viewer is attached the
events are simply discarded, so the pipeline has zero overhead.
"""

from __future__ import annotations

import json
import queue
import time
from dataclasses import asdict, dataclass, field
from typing import Any


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
        self._subscribers: list[queue.Queue[Event | None]] = []

    def subscribe(self) -> queue.Queue[Event | None]:
        q: queue.Queue[Event | None] = queue.Queue(maxsize=256)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    def emit(self, kind: str, stage: str, **data) -> None:
        ev = Event(kind=kind, stage=stage, data=data)
        for q in self._subscribers:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass  # slow consumer — drop the event

    def close(self) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(None)
            except queue.Full:
                pass


# Global singleton — agents import this and call `bus.emit(...)`.
bus = EventBus()
