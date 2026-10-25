"""No devices attached. Reads fail explicitly instead of inventing samples."""

from __future__ import annotations

from mirae.hardware.base import HardwareBundle


class UnavailableMotors:
    def set_speeds(self, left: float, right: float) -> None:
        raise RuntimeError("no motor driver is attached")

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


class UnavailableEncoders:
    def read_counts(self) -> tuple[int, int]:
        raise RuntimeError("no encoders are attached")

    def close(self) -> None:
        pass


class UnavailableRangeSensor:
    def read_mm(self) -> float | None:
        raise RuntimeError("no range sensor is attached")

    def close(self) -> None:
        pass


def disconnected_hardware() -> HardwareBundle:
    return HardwareBundle(UnavailableMotors(), UnavailableEncoders(), UnavailableRangeSensor())
