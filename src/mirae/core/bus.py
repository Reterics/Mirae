"""In-process publish/subscribe bus.

Subsystems communicate through topics instead of calling each other, so any one
of them can be replaced (or moved to another process later) without touching
the rest. Slow subscribers drop their oldest messages; publishers never block.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: defaultdict[str, set[asyncio.Queue[Any]]] = defaultdict(set)
        self._latest: dict[str, Any] = {}

    def publish(self, topic: str, message: Any) -> None:
        self._latest[topic] = message
        for queue in self._subscribers[topic]:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)

    def latest(self, topic: str, default: Any = None) -> Any:
        return self._latest.get(topic, default)

    @asynccontextmanager
    async def subscribe(self, topic: str, maxsize: int = 16) -> AsyncIterator[asyncio.Queue[Any]]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)
        self._subscribers[topic].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[topic].discard(queue)


class Topics:
    TELEMETRY = "telemetry"
    INTENT = "behavior.intent"
    STATE = "behavior.state"
    SAY = "speech.say"
    TRANSCRIPT = "speech.transcript"
    DETECTIONS = "vision.detections"
