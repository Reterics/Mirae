"""Robot runtime: wires the subsystems together and runs the real-time loops.

One asyncio process. The control loop owns the motors; blocking I/O (I2C range
reads, and later camera/STT inference) runs in worker threads and reports back
through the governor or the event bus.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from mirae.ai.planner import IntentPlanner
from mirae.ai.providers import build_provider
from mirae.behavior.engine import BehaviorEngine
from mirae.config import MiraeConfig
from mirae.core.bus import EventBus, Topics
from mirae.core.clock import Clock, MonotonicClock
from mirae.drive.controller import DriveController, DriveState
from mirae.hardware.base import HardwareBundle
from mirae.hardware.sim import SimWorld, build_sim
from mirae.safety.governor import SafetyGovernor

log = logging.getLogger(__name__)


class Robot:
    def __init__(
        self,
        config: MiraeConfig,
        *,
        hardware: HardwareBundle | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config
        self.clock: Clock = clock or MonotonicClock()
        self.bus = EventBus()
        self.sim_world: SimWorld | None = None

        if hardware is None:
            if config.hardware.backend == "sim":
                hardware, self.sim_world = build_sim(config.drive, self.clock)
            else:
                from mirae.hardware.pi import build_pi

                hardware = build_pi(config.hardware)
        self.hardware = hardware

        self.governor = SafetyGovernor(config.safety, self.clock)
        self.drive = DriveController(
            config.drive, hardware.motors, hardware.encoders, self.governor
        )
        self.behavior = BehaviorEngine(self.governor, self.bus)
        self._provider = build_provider(config.ai)
        self.planner = IntentPlanner(self._provider) if self._provider else None

        self.last_drive: DriveState | None = None
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        log.info("starting Mirae (%s backend)", self.config.hardware.backend)
        self._tasks = [
            asyncio.create_task(self._control_loop(), name="control"),
            asyncio.create_task(self._range_loop(), name="range"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        try:
            for task in self._tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    log.exception("task %s crashed", task.get_name())
        finally:
            self._tasks = []
            try:
                self.hardware.close()
            finally:
                if self._provider:
                    await self._provider.aclose()
            log.info("stopped")

    @property
    def healthy(self) -> bool:
        """True while every runtime loop is still running."""
        return bool(self._tasks) and not any(task.done() for task in self._tasks)

    async def _control_loop(self) -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / self.config.drive.control_hz
        next_tick = loop.time()
        try:
            while True:
                self.last_drive = self.drive.step()
                self.behavior.tick()
                self.bus.publish(Topics.TELEMETRY, self.telemetry())
                next_tick += period
                await asyncio.sleep(max(0.0, next_tick - loop.time()))
        finally:
            # Whatever ends this loop (shutdown or a bug), the motors stop.
            self.hardware.motors.stop()

    async def _range_loop(self) -> None:
        period = 1.0 / self.config.hardware.tof.poll_hz
        sensor = self.hardware.range_sensor
        while True:
            try:
                distance = await asyncio.to_thread(sensor.read_mm)
            except Exception:
                log.exception("range sensor read failed")
                distance = None
            self.governor.update_range(distance)
            await asyncio.sleep(period)

    def telemetry(self) -> dict[str, Any]:
        drive = self.last_drive
        return {
            "time": self.clock.now(),
            "backend": self.config.hardware.backend,
            "behavior": self.behavior.state.value,
            "safety": asdict(drive.safety) if drive else None,
            "wheels": asdict(drive.output) if drive else None,
            "encoders": list(drive.counts) if drive else None,
            "pose": asdict(drive.pose) if drive else None,
        }
