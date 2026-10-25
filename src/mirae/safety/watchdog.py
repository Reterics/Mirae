"""Best-effort motor cutoff independent of the asyncio loop.

A Python thread cannot protect against power loss, a wedged GPIO driver, or a
native call that holds the GIL. A hardware heartbeat/cutoff is still required
before unattended operation on the robot.
"""

from __future__ import annotations

import logging
import threading
import time

from mirae.hardware.base import MotorDriver

log = logging.getLogger(__name__)


class MotorWatchdog:
    def __init__(self, motors: MotorDriver, timeout_s: float) -> None:
        self._motors = motors
        self._timeout_s = timeout_s
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None
        self._closing = False
        self._fault: str | None = None
        self._heartbeat_until = 0.0
        self._command_until: float | None = None

    @property
    def fault(self) -> str | None:
        with self._condition:
            return self._fault

    def start(self) -> None:
        with self._condition:
            if self._thread is not None:
                raise RuntimeError("motor watchdog already started")
            self._heartbeat_until = time.monotonic() + self._timeout_s
            self._thread = threading.Thread(target=self._run, name="motor-watchdog", daemon=True)
            self._thread.start()

    def write(self, left: float, right: float, valid_for_s: float) -> None:
        # Serialize every motor write with cutoff: a late control tick must never
        # race a watchdog stop and restart the wheels after a latched fault.
        with self._condition:
            now = time.monotonic()
            if self._closing or self._fault or self._thread is None:
                raise RuntimeError(self._fault or "motor watchdog is not running")
            if now >= self._heartbeat_until:
                self._fault = "control heartbeat expired"
                self._motors.stop()
                raise RuntimeError(self._fault)
            if valid_for_s <= 0.0:
                left = right = 0.0
            self._motors.set_speeds(left, right)
            self._heartbeat_until = now + self._timeout_s
            self._command_until = now + valid_for_s if left or right else None
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._command_until = None
            self._motors.stop()
            self._condition.notify_all()

    def close(self) -> None:
        try:
            with self._condition:
                self._closing = True
                self._condition.notify_all()
                self._motors.stop()
        finally:
            if self._thread is not None and self._thread.ident is not None:
                self._thread.join(timeout=self._timeout_s + 0.1)
                if self._thread.is_alive():
                    raise RuntimeError("motor watchdog failed to stop")

    def _run(self) -> None:
        with self._condition:
            try:
                while not self._closing and self._fault is None:
                    now = time.monotonic()
                    if now >= self._heartbeat_until:
                        self._fault = "control heartbeat expired"
                        self._motors.stop()
                        break
                    if self._command_until is not None and now >= self._command_until:
                        self._motors.stop()
                        self._command_until = None
                    deadline = min(
                        self._heartbeat_until,
                        self._command_until if self._command_until is not None else float("inf"),
                    )
                    self._condition.wait(timeout=max(0.0, deadline - time.monotonic()))
            except Exception:
                self._fault = "motor watchdog I/O failed"
                log.exception(self._fault)
