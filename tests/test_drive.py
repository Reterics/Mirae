import math

import pytest

from mirae.config import DriveConfig, SafetyConfig
from mirae.core.clock import FakeClock
from mirae.drive.controller import DriveController
from mirae.drive.kinematics import Odometry, mix
from mirae.hardware.sim import build_sim
from mirae.safety.governor import SafetyGovernor


def test_mix_straight_and_spin() -> None:
    assert mix(0.5, 0.0) == (0.5, 0.5)
    assert mix(0.0, 0.5) == (-0.5, 0.5)


def test_mix_saturation_preserves_ratio() -> None:
    left, right = mix(1.0, 0.5)
    assert right == 1.0
    assert left == pytest.approx(1.0 / 3.0)


def test_odometry_straight_line() -> None:
    odo = Odometry(wheel_diameter_mm=42.0, track_width_mm=141.0, counts_per_rev=1000.0)
    odo.update((0, 0))
    pose = odo.update((1000, 1000))
    assert pose.x_m == pytest.approx(math.pi * 0.042)
    assert pose.y_m == pytest.approx(0.0)
    assert pose.theta_rad == pytest.approx(0.0)


def test_odometry_spin_in_place() -> None:
    odo = Odometry(wheel_diameter_mm=42.0, track_width_mm=141.0, counts_per_rev=1000.0)
    odo.update((0, 0))
    # Quarter turn: each wheel travels a quarter of the track circle.
    counts = round(math.pi * 141.0 / 4 / (math.pi * 42.0) * 1000)
    pose = odo.update((-counts, counts))
    assert pose.theta_rad == pytest.approx(math.pi / 2, abs=0.01)
    assert pose.x_m == pytest.approx(0.0, abs=1e-6)


def test_controller_drives_sim_forward() -> None:
    clock = FakeClock()
    drive_cfg = DriveConfig()
    hardware, world = build_sim(drive_cfg, clock)
    governor = SafetyGovernor(SafetyConfig(), clock)
    controller = DriveController(drive_cfg, hardware.motors, hardware.encoders, governor)

    controller.step()
    for _ in range(25):  # 0.5 s: past the default ramp to 0.5 (1.5 per second)
        governor.update_range(world.range_mm)
        governor.command(0.5, 0.5)
        clock.advance(0.02)
        state = controller.step()

    assert state.output.left == 0.5
    assert state.pose.x_m > 0.0
    assert state.pose.y_m == pytest.approx(0.0)
