"""Injectable time source, so timing logic is testable without sleeping."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Monotonic time in seconds."""
        ...


class MonotonicClock:
    def now(self) -> float:
        return time.monotonic()


class FakeClock:
    """Manually advanced clock for tests and the simulator."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds
