from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from typing import Protocol


class MotorDriver(Protocol):
    def set_speeds(self, left: float, right: float) -> None:
        """Normalized wheel duty cycles in [-1, 1]. Positive drives forward."""
        ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class WheelEncoders(Protocol):
    def read_counts(self) -> tuple[int, int]:
        """Cumulative (left, right) counts. Positive is forward."""
        ...

    def close(self) -> None: ...


class RangeSensor(Protocol):
    def read_mm(self) -> float | None:
        """Distance to the nearest obstacle ahead, or None if there is no valid reading.

        May block for one measurement period; the runtime calls it from a worker thread.
        """
        ...

    def close(self) -> None: ...


@dataclass
class HardwareBundle:
    motors: MotorDriver
    encoders: WheelEncoders
    range_sensor: RangeSensor

    def close(self, *, close_range_sensor: bool = True) -> None:
        # All cleanup runs even when one device's stop/close raises.
        with ExitStack() as cleanup:
            if close_range_sensor:
                cleanup.callback(self.range_sensor.close)
            cleanup.callback(self.encoders.close)
            cleanup.callback(self.motors.close)
            self.motors.stop()
