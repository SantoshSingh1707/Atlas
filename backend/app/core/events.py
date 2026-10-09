from __future__ import annotations

import queue
from collections.abc import Iterator

from app.schemas import RunEvent

_TERMINAL_STEPS = {"done", "error"}


class EventBus:
    """Per-run pub/sub. Streams events until a terminal step closes the run."""

    def __init__(self) -> None:
        self._queues: dict[str, queue.Queue[RunEvent]] = {}

    def _queue(self, run_id: str) -> queue.Queue[RunEvent]:
        return self._queues.setdefault(run_id, queue.Queue(maxsize=1000))

    def publish(self, event: RunEvent) -> None:
        self._queue(event.run_id).put(event)

    def stream(self, run_id: str) -> Iterator[RunEvent]:
        events = self._queue(run_id)
        while True:
            event = events.get()
            yield event
            if event.step in _TERMINAL_STEPS:
                break
        self.close(run_id)

    def close(self, run_id: str) -> None:
        self._queues.pop(run_id, None)
