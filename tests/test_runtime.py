import asyncio
import threading

import httpx
import pytest

from mirae.api.app import create_app
from mirae.config import HardwareConfig, SafetyConfig, ToFConfig, load_config
from mirae.core.clock import MonotonicClock
from mirae.hardware.base import HardwareBundle
from mirae.hardware.range_worker import RangeWorker
from mirae.robot import Robot
from mirae.safety.watchdog import MotorWatchdog


class RecordingMotors:
    def __init__(self) -> None:
        self.output = (0.0, 0.0)
        self.moving = threading.Event()
        self.stopped = threading.Event()
        self.closed = False

    def set_speeds(self, left: float, right: float) -> None:
        self.output = (left, right)
        if left or right:
            self.moving.set()

    def stop(self) -> None:
        self.output = (0.0, 0.0)
        self.stopped.set()

    def close(self) -> None:
        self.closed = True


class Encoders:
    def read_counts(self) -> tuple[int, int]:
        return (0, 0)

    def close(self) -> None:
        pass


class BlockingRange:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.reading = False
        self.closed_during_read = False

    def read_mm(self) -> float | None:
        self.reading = True
        self.started.set()
        self.release.wait(timeout=3.0)
        self.reading = False
        return 2000.0

    def close(self) -> None:
        self.closed_during_read = self.reading
        self.closed.set()


def test_watchdog_cuts_motor_output_without_an_event_loop() -> None:
    motors = RecordingMotors()
    watchdog = MotorWatchdog(motors, timeout_s=0.1)
    watchdog.start()
    try:
        watchdog.write(-0.3, -0.3, valid_for_s=5.0)
        assert motors.stopped.wait(timeout=1.0)
        assert motors.output == (0.0, 0.0)
        assert watchdog.fault == "control heartbeat expired"
        with pytest.raises(RuntimeError, match="heartbeat"):
            watchdog.write(-0.3, -0.3, valid_for_s=5.0)
    finally:
        watchdog.close()


def test_command_expiry_stops_without_latching_a_runtime_fault() -> None:
    motors = RecordingMotors()
    watchdog = MotorWatchdog(motors, timeout_s=1.0)
    watchdog.start()
    try:
        watchdog.write(-0.3, -0.3, valid_for_s=0.03)
        assert motors.stopped.wait(timeout=0.8)
        assert motors.output == (0.0, 0.0)
        assert watchdog.fault is None
        watchdog.write(-0.2, -0.2, valid_for_s=0.2)
        assert motors.output == (-0.2, -0.2)
    finally:
        watchdog.stop()
        watchdog.close()


def test_range_worker_never_closes_an_active_read() -> None:
    sensor = BlockingRange()
    worker = RangeWorker(sensor, MonotonicClock(), poll_hz=20, timeout_s=0.03)
    worker.start()
    try:
        assert sensor.started.wait(timeout=1.0)
        worker.close()
        assert not sensor.closed.is_set()
    finally:
        sensor.release.set()
    assert sensor.closed.wait(timeout=1.0)
    assert not sensor.closed_during_read


def test_blocked_sensor_fault_stops_robot_and_rejects_movement(test_token: str) -> None:
    async def scenario() -> None:
        sensor = BlockingRange()
        motors = RecordingMotors()
        config = load_config("local").model_copy(
            update={
                "hardware": HardwareConfig(backend="pi", tof=ToFConfig(read_timeout_s=0.03)),
                "safety": SafetyConfig(ramp_per_s=None),
            }
        )
        robot = Robot(config, hardware=HardwareBundle(motors, Encoders(), sensor))
        app = create_app(robot)
        try:
            await robot.start()
            robot.governor.command(-0.3, -0.3, duration_s=5.0)
            await asyncio.wait_for(robot.wait_failure(), timeout=1.0)
            assert not robot.healthy
            assert robot.governor.estopped
            assert motors.output == (0.0, 0.0)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {test_token}"},
            ) as client:
                assert (await client.get("/api/health")).status_code == 503
                assert (await client.post("/api/drive", json={"linear": -0.3})).status_code == 503
                assert (await client.post("/api/estop/release")).status_code == 503
        finally:
            sensor.release.set()
            await robot.stop()
            await robot.stop()  # cleanup is safe after the server lifespan already stopped it
        assert motors.closed
        assert sensor.closed.is_set()
        assert not sensor.closed_during_read

    asyncio.run(scenario())


def test_deadman_still_stops_motors_while_asyncio_is_blocked() -> None:
    async def scenario() -> None:
        sensor = BlockingRange()
        sensor.release.set()
        motors = RecordingMotors()
        config = load_config("local").model_copy(
            update={
                "safety": SafetyConfig(ramp_per_s=None),
                "hardware": HardwareConfig(backend="pi"),
            }
        )
        robot = Robot(config, hardware=HardwareBundle(motors, Encoders(), sensor))
        try:
            await robot.start()
            robot.governor.command(-0.3, -0.3, duration_s=0.05)
            await asyncio.to_thread(motors.moving.wait, 1.0)
            assert motors.moving.is_set()
            # Deliberately block this thread: the event loop cannot run its deadman.
            assert motors.stopped.wait(timeout=1.0)
            assert motors.output == (0.0, 0.0)
        finally:
            await robot.stop()

    asyncio.run(scenario())
