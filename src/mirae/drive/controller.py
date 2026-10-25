from __future__ import annotations

from dataclasses import dataclass, replace

from mirae.config import DriveConfig
from mirae.drive.kinematics import Odometry, Pose
from mirae.hardware.base import MotorDriver, WheelEncoders
from mirae.safety.governor import SafetyGovernor, SafetyStatus, WheelCommand
from mirae.safety.watchdog import MotorWatchdog


@dataclass(frozen=True)
class DriveState:
    output: WheelCommand
    safety: SafetyStatus
    counts: tuple[int, int]
    pose: Pose


class DriveController:
    """Runs once per control tick: governor -> motors, encoders -> odometry.

    Open loop for now. Per-wheel PID on encoder velocity belongs here (V0.2),
    between the governor output and ``set_speeds``.
    """

    def __init__(
        self,
        cfg: DriveConfig,
        motors: MotorDriver,
        encoders: WheelEncoders,
        governor: SafetyGovernor,
        *,
        watchdog: MotorWatchdog | None = None,
    ) -> None:
        self._motors = motors
        self._encoders = encoders
        self._governor = governor
        self._watchdog = watchdog
        self._odometry = Odometry(
            cfg.wheel_diameter_mm, cfg.track_width_mm, cfg.encoder_counts_per_rev
        )

    def step(self) -> DriveState:
        output, safety = self._governor.output()
        if self._watchdog is None:
            self._motors.set_speeds(output.left, output.right)
        else:
            self._watchdog.write(output.left, output.right, self._governor.remaining_s)
        counts = self._encoders.read_counts()
        pose = self._odometry.update(counts)
        return DriveState(output=output, safety=safety, counts=counts, pose=replace(pose))
