from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float | None
    # Normalized [0, 1] box: x, y of the top-left corner, then width, height.
    box: tuple[float, float, float, float]
    match_distance: float | None = None
    kind: str = "object"  # "object" or "face"

    @property
    def center_x(self) -> float:
        return self.box[0] + self.box[2] / 2.0


class CameraSource(Protocol):
    def read(self) -> Any | None:
        """Latest frame as an HxWx3 BGR numpy array, or None."""
        ...

    def close(self) -> None: ...


class Detector(Protocol):
    def detect(self, frame: Any) -> list[Detection]: ...


class NullCamera:
    def read(self) -> Any | None:
        return None

    def close(self) -> None:
        pass


class NullDetector:
    def detect(self, frame: Any) -> list[Detection]:
        return []
