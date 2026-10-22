from __future__ import annotations

import math
from dataclasses import dataclass


def mix(linear: float, angular: float) -> tuple[float, float]:
    """Normalized (linear, angular) in [-1, 1] -> (left, right) wheel speeds in [-1, 1].

    Positive angular turns left (counter-clockwise). When a wheel would exceed
    full speed, both are scaled together so the turn radius is preserved.
    """
    left = linear - angular
    right = linear + angular
    peak = max(abs(left), abs(right), 1.0)
    return left / peak, right / peak


@dataclass
class Pose:
    x_m: float = 0.0
    y_m: float = 0.0
    theta_rad: float = 0.0


class Odometry:
    def __init__(self, wheel_diameter_mm: float, track_width_mm: float, counts_per_rev: float):
        self._m_per_count = math.pi * wheel_diameter_mm / 1000.0 / counts_per_rev
        self._track_m = track_width_mm / 1000.0
        self._last: tuple[int, int] | None = None
        self.pose = Pose()

    def update(self, counts: tuple[int, int]) -> Pose:
        if self._last is None:
            self._last = counts
            return self.pose
        d_left = (counts[0] - self._last[0]) * self._m_per_count
        d_right = (counts[1] - self._last[1]) * self._m_per_count
        self._last = counts

        distance = (d_left + d_right) / 2.0
        d_theta = (d_right - d_left) / self._track_m
        mid_theta = self.pose.theta_rad + d_theta / 2.0
        self.pose.x_m += distance * math.cos(mid_theta)
        self.pose.y_m += distance * math.sin(mid_theta)
        self.pose.theta_rad = math.atan2(
            math.sin(self.pose.theta_rad + d_theta), math.cos(self.pose.theta_rad + d_theta)
        )
        return self.pose
