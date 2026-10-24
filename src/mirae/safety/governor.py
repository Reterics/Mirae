"""Safety governor: every wheel command passes through here before the motors.

Rules, applied on every control tick:
  * e-stop latched           -> zero output; commands are ignored until released,
                                and release never resumes an earlier command
  * command expired          -> zero output (deadman; clients must keep re-sending)
  * speed above max_speed    -> clamped
  * forward motion with the obstacle closer than stop_distance, or no recent
    range reading           -> forward component removed (turning and reversing still allowed)
  * obstacle inside slow_distance -> forward component scaled down linearly
  * a wheel speeding up      -> limited to ramp_per_s; slowing down and stopping are
                                immediate, and a reversal starts again from zero
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from mirae.config import SafetyConfig
from mirae.core.clock import Clock

# A gap longer than this between two outputs (a stalled loop) counts as this long for the ramp,
# so a late tick can't jump straight to full speed.
_MAX_RAMP_DT_S = 0.1


def _ramp(previous: float, target: float, step: float) -> float:
    if previous * target < 0.0:  # reversing: drop to zero first
        previous = 0.0
    if abs(target) <= abs(previous):
        return target
    return math.copysign(min(abs(target), abs(previous) + step), target)


@dataclass(frozen=True)
class WheelCommand:
    left: float = 0.0
    right: float = 0.0


@dataclass(frozen=True)
class SafetyStatus:
    estop: bool
    limit: str | None
    range_mm: float | None


class SafetyGovernor:
    def __init__(self, cfg: SafetyConfig, clock: Clock) -> None:
        self._cfg = cfg
        self._clock = clock
        self._target = WheelCommand()
        self._deadline = 0.0
        self._estop = False
        self._range_mm: float | None = None
        self._range_at = float("-inf")
        self._last = WheelCommand()
        self._last_at = clock.now()

    @property
    def estopped(self) -> bool:
        return self._estop

    def command(self, left: float, right: float, duration_s: float | None = None) -> None:
        if self._estop:
            return
        duration = self._cfg.command_timeout_s if duration_s is None else duration_s
        duration = max(0.0, min(duration, self._cfg.max_command_duration_s))
        self._target = WheelCommand(left, right)
        self._deadline = self._clock.now() + duration

    def stop(self) -> None:
        self._target = WheelCommand()
        self._deadline = 0.0

    def estop(self) -> None:
        self._estop = True
        self.stop()

    def release(self) -> None:
        # Releasing never resumes motion; a fresh command is required.
        self._estop = False
        self.stop()

    def update_range(self, distance_mm: float | None) -> None:
        self._range_mm = distance_mm
        self._range_at = self._clock.now()

    def _current_range(self) -> float | None:
        if self._clock.now() - self._range_at > self._cfg.range_stale_s:
            return None
        return self._range_mm

    def output(self) -> tuple[WheelCommand, SafetyStatus]:
        cfg = self._cfg
        range_mm = self._current_range()
        now = self._clock.now()
        dt = min(max(now - self._last_at, 0.0), _MAX_RAMP_DT_S)
        self._last_at = now

        def result(cmd: WheelCommand, limit: str | None) -> tuple[WheelCommand, SafetyStatus]:
            self._last = cmd
            return cmd, SafetyStatus(estop=self._estop, limit=limit, range_mm=range_mm)

        if self._estop:
            return result(WheelCommand(), "estop")
        if now >= self._deadline:
            return result(WheelCommand(), None)

        limit: str | None = None
        left = max(-cfg.max_speed, min(cfg.max_speed, self._target.left))
        right = max(-cfg.max_speed, min(cfg.max_speed, self._target.right))
        if (left, right) != (self._target.left, self._target.right):
            limit = "max_speed"

        forward = (left + right) / 2.0
        if forward > 0.0:
            if range_mm is None or range_mm <= cfg.stop_distance_mm:
                left, right = left - forward, right - forward
                limit = "no_range" if range_mm is None else "obstacle"
            elif range_mm < cfg.slow_distance_mm:
                span = cfg.slow_distance_mm - cfg.stop_distance_mm
                scale = (range_mm - cfg.stop_distance_mm) / span
                cut = forward * (1.0 - scale)
                left, right = left - cut, right - cut
                limit = "slow_zone"

        if cfg.ramp_per_s is not None:
            step = cfg.ramp_per_s * dt
            ramped = (_ramp(self._last.left, left, step), _ramp(self._last.right, right, step))
            if ramped != (left, right) and limit is None:
                limit = "ramp"
            left, right = ramped

        return result(WheelCommand(left, right), limit)
