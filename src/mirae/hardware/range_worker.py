"""One sensor owner: a blocked read is never raced by close() on another thread."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from mirae.core.clock import Clock
from mirae.hardware.base import RangeSensor

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RangeReading:
    sequence: int
    distance_mm: float | None
    observed_at: float


class RangeWorker:
    def __init__(self, sensor: RangeSensor, clock: Clock, poll_hz: float, timeout_s: float) -> None:
        self._sensor = sensor
        self._clock = clock
        self._period = 1.0 / poll_hz
        self._timeout_s = timeout_s
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._reading_since: float | None = None
        self._latest: RangeReading | None = None
        self._thread = threading.Thread(target=self._run, name="range-sensor", daemon=True)

    def start(self) -> None:
        self._thread.start()

    @property
    def healthy(self) -> bool:
        with self._lock:
            return self._thread.is_alive() and (
                self._reading_since is None
                or time.monotonic() - self._reading_since < self._timeout_s
            )

    def latest(self) -> RangeReading | None:
        with self._lock:
            return self._latest

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._timeout_s)
        if self._thread.is_alive():
            log.error("range read is stuck; sensor close deferred until its worker returns")

    def _run(self) -> None:
        sequence = 0
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                with self._lock:
                    self._reading_since = started
                try:
                    distance = self._sensor.read_mm()
                except Exception:
                    log.exception("range sensor read failed")
                    distance = None
                sequence += 1
                reading = RangeReading(sequence, distance, self._clock.now())
                with self._lock:
                    self._latest = reading
                    self._reading_since = None
                self._stop.wait(max(0.0, self._period - (time.monotonic() - started)))
        finally:
            try:
                self._sensor.close()
            except Exception:
                log.exception("range sensor close failed")
