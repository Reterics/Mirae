"""Simulated hardware: a point robot whose encoders follow the commanded speeds."""

from __future__ import annotations

from mirae.config import DriveConfig
from mirae.core.clock import Clock
from mirae.hardware.base import HardwareBundle


class SimWorld:
    def __init__(self, drive: DriveConfig, clock: Clock) -> None:
        self._clock = clock
        self._counts_per_s_at_full = drive.max_wheel_rpm / 60.0 * drive.encoder_counts_per_rev
        self._last = clock.now()
        self._counts = [0.0, 0.0]
        self.speeds = (0.0, 0.0)
        # Settable from tests or the /api/sim/range endpoint.
        self.range_mm: float | None = 2000.0

    def advance(self) -> None:
        now = self._clock.now()
        dt = now - self._last
        self._last = now
        self._counts[0] += self.speeds[0] * self._counts_per_s_at_full * dt
        self._counts[1] += self.speeds[1] * self._counts_per_s_at_full * dt

    def counts(self) -> tuple[int, int]:
        self.advance()
        return int(self._counts[0]), int(self._counts[1])


class SimMotorDriver:
    def __init__(self, world: SimWorld) -> None:
        self._world = world

    def set_speeds(self, left: float, right: float) -> None:
        self._world.advance()
        self._world.speeds = (left, right)

    def stop(self) -> None:
        self.set_speeds(0.0, 0.0)

    def close(self) -> None:
        pass


class SimEncoders:
    def __init__(self, world: SimWorld) -> None:
        self._world = world

    def read_counts(self) -> tuple[int, int]:
        return self._world.counts()

    def close(self) -> None:
        pass


class SimRangeSensor:
    def __init__(self, world: SimWorld) -> None:
        self._world = world

    def read_mm(self) -> float | None:
        return self._world.range_mm

    def close(self) -> None:
        pass


def build_sim(drive: DriveConfig, clock: Clock) -> tuple[HardwareBundle, SimWorld]:
    world = SimWorld(drive, clock)
    bundle = HardwareBundle(
        motors=SimMotorDriver(world),
        encoders=SimEncoders(world),
        range_sensor=SimRangeSensor(world),
    )
    return bundle, world
