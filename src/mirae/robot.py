"""Robot runtime: wires the subsystems together and runs the real-time loops.

One asyncio process, with dedicated sensor and motor watchdog threads. Inference
must run outside the control loop. The watchdog is a software fallback, not a
replacement for a physical motor cutoff.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
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
from mirae.hardware.disconnected import disconnected_hardware
from mirae.hardware.range_worker import RangeWorker
from mirae.pipeline.workers import SpeechWorker, VisionWorker
from mirae.safety.governor import SafetyGovernor
from mirae.safety.watchdog import MotorWatchdog

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
        self._started_at = self.clock.now()
        self.hardware_error: str | None = None
        self.hardware_connected = config.hardware.backend == "pi"

        if hardware is None:
            if config.hardware.backend == "pi":
                from mirae.hardware.pi import build_pi

                try:
                    hardware = build_pi(config.hardware)
                except Exception as exc:
                    self.hardware_error = f"{type(exc).__name__}: {exc}"
                    self.hardware_connected = False
                    hardware = disconnected_hardware()
                    log.exception(
                        "physical hardware initialization failed; administration remains available"
                    )
            else:
                hardware = disconnected_hardware()
        self.hardware = hardware

        try:
            self.governor = SafetyGovernor(config.safety, self.clock)
            self.watchdog = MotorWatchdog(hardware.motors, config.safety.motor_watchdog_s)
            self.drive = DriveController(
                config.drive,
                hardware.motors,
                hardware.encoders,
                self.governor,
                watchdog=self.watchdog,
            )
            self.behavior = BehaviorEngine(self.governor, self.bus)
            self._provider = build_provider(config.ai)
            self.planner = IntentPlanner(self._provider) if self._provider else None
        except BaseException:
            hardware.close()
            raise

        self.last_drive: DriveState | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._range_worker = RangeWorker(
            hardware.range_sensor,
            self.clock,
            config.hardware.tof.poll_hz,
            config.hardware.tof.read_timeout_s,
        )
        self._range_owned = False
        self._stopping = False
        self._closed = False
        self._fault: str | None = None
        self._failure = asyncio.Event()
        self._last_control_at: float | None = None
        self._max_tick_lateness_s = 0.0
        self._missed_ticks = 0
        self.maintenance = False
        self.vision = VisionWorker(config.vision)
        self.speech = SpeechWorker(config.speech)
        self._perception_samples = {"vision": 0, "speech": 0}

    async def start(self) -> None:
        if self._tasks or self._closed:
            raise RuntimeError("robot already started or closed")
        log.info("starting Mirae (%s backend)", self.config.hardware.backend)
        try:
            if self.hardware_connected:
                self.watchdog.start()
                self._range_worker.start()
                self._range_owned = True
                self._tasks = [
                    asyncio.create_task(self._control_loop(), name="control"),
                    asyncio.create_task(self._range_loop(), name="range"),
                ]
            else:
                self._tasks = [asyncio.create_task(self._services_loop(), name="services")]
            for task in self._tasks:
                task.add_done_callback(self._task_done)
            self.vision.start()
            self.speech.start()
        except BaseException:
            await self.stop()
            raise

    async def wait_failure(self) -> None:
        await self._failure.wait()

    def halt(self, *, estop: bool = False) -> None:
        if estop:
            self.governor.estop()
        else:
            self.governor.stop()
        self.watchdog.stop()

    @property
    def fault(self) -> str | None:
        return self._fault or self.watchdog.fault

    def _task_done(self, task: asyncio.Task[None]) -> None:
        error = None if task.cancelled() else task.exception()
        if self._stopping or self._fault:
            return
        self._fault = f"{task.get_name()} loop stopped"
        log.error(
            self._fault, exc_info=(type(error), error, error.__traceback__) if error else None
        )
        self.governor.estop()
        try:
            self.watchdog.stop()
        except Exception:
            log.exception("motor stop after runtime failure failed")
        self._failure.set()
        for sibling in self._tasks:
            if sibling is not task:
                sibling.cancel()

    async def stop(self) -> None:
        if self._closed:
            return
        self._stopping = True
        self._closed = True
        self.governor.estop()
        for task in self._tasks:
            task.cancel()

        async def join_tasks() -> None:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []

        # Registered in reverse order; every cleanup still runs after an error.
        async with AsyncExitStack() as cleanup:
            if self._provider:
                cleanup.push_async_callback(self._provider.aclose)
            cleanup.callback(self.hardware.close, close_range_sensor=not self._range_owned)
            if self._range_owned:
                cleanup.push_async_callback(asyncio.to_thread, self._range_worker.close)
            cleanup.push_async_callback(asyncio.to_thread, self.vision.close)
            cleanup.push_async_callback(asyncio.to_thread, self.speech.close)
            cleanup.callback(self.watchdog.close)
            cleanup.push_async_callback(join_tasks)
            self.watchdog.stop()
        log.info("stopped")

    @property
    def healthy(self) -> bool:
        """Include actual progress and independent worker/watchdog health."""
        return (
            not self._stopping
            and not self.maintenance
            and self.fault is None
            and bool(self._tasks)
            and not any(task.done() for task in self._tasks)
            and (not self.hardware_connected or self._range_worker.healthy)
            and self._last_control_at is not None
            and self.clock.now() - self._last_control_at
            < (
                self.config.safety.motor_watchdog_s
                if self.hardware_connected
                else max(1.0, 2.0 / self.config.api.telemetry_hz)
            )
        )

    def _publish_perception(self) -> None:
        for name, worker in (("vision", self.vision), ("speech", self.speech)):
            sample = worker.snapshot()
            if sample["samples"] != self._perception_samples[name]:
                self._perception_samples[name] = sample["samples"]
                topic = Topics.DETECTIONS if name == "vision" else Topics.TRANSCRIPT
                self.bus.publish(
                    topic,
                    sample.get("detections", [])
                    if name == "vision"
                    else sample.get("transcript", ""),
                )

    async def _services_loop(self) -> None:
        """Run actual local services without sampling nonexistent robot devices."""
        while True:
            self._publish_perception()
            self._last_control_at = self.clock.now()
            self.bus.publish(Topics.TELEMETRY, self.telemetry())
            await asyncio.sleep(1.0 / self.config.api.telemetry_hz)

    async def _control_loop(self) -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / self.config.drive.control_hz
        next_tick = loop.time()
        next_publish = next_tick
        try:
            while True:
                self._max_tick_lateness_s = max(self._max_tick_lateness_s, loop.time() - next_tick)
                self.last_drive = self.drive.step()
                self.behavior.tick()
                self._publish_perception()
                self._last_control_at = self.clock.now()
                if loop.time() >= next_publish:
                    self.bus.publish(Topics.TELEMETRY, self.telemetry())
                    next_publish = loop.time() + 1.0 / self.config.api.telemetry_hz
                next_tick += period
                now = loop.time()
                if next_tick <= now:
                    self._missed_ticks += 1 + int((now - next_tick) / period)
                    next_tick = now + period
                await asyncio.sleep(max(0.0, next_tick - loop.time()))
        finally:
            # Whatever ends this loop (shutdown or a bug), the motors stop.
            self.watchdog.stop()

    async def _range_loop(self) -> None:
        period = 1.0 / self.config.hardware.tof.poll_hz
        last_sequence = 0
        while True:
            if not self._range_worker.healthy:
                raise RuntimeError("range sensor worker stopped or read timed out")
            reading = self._range_worker.latest()
            if reading is not None and reading.sequence != last_sequence:
                self.governor.update_range(reading.distance_mm, observed_at=reading.observed_at)
                last_sequence = reading.sequence
            await asyncio.sleep(period)

    def telemetry(self) -> dict[str, Any]:
        drive = self.last_drive
        return {
            "time": self.clock.now(),
            "backend": self.config.hardware.backend,
            "hardware_ready": self.hardware_connected,
            "hardware_error": self.hardware_error,
            "perception": {"vision": self.vision.snapshot(), "speech": self.speech.snapshot()},
            "runtime": {
                "healthy": self.healthy,
                "uptime_s": max(0.0, self.clock.now() - self._started_at),
                "fault": self.fault,
                "control_running": self.hardware_connected,
                "max_tick_lateness_s": self._max_tick_lateness_s
                if self.hardware_connected
                else None,
                "missed_ticks": self._missed_ticks if self.hardware_connected else None,
            },
            "behavior": self.behavior.state.value,
            "safety": asdict(drive.safety) if drive else None,
            "wheels": asdict(drive.output) if drive else None,
            "encoders": list(drive.counts) if drive else None,
            "pose": asdict(drive.pose) if drive else None,
        }
