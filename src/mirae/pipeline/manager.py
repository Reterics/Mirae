"""Real connection checks, local dependency inspection and staged device settings."""

from __future__ import annotations

import asyncio
import base64
import importlib
import importlib.metadata
import importlib.util
import json
import platform
import socket
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import httpx

from mirae.ai.planner import IntentPlanner
from mirae.ai.providers import build_provider
from mirae.api.accounts import AccountError, AuthStore
from mirae.config import MiraeConfig
from mirae.pipeline.devices import audio_devices, camera_devices, open_input
from mirae.pipeline.jobs import PACKAGES, JobRunner
from mirae.pipeline.models import ModelLibrary
from mirae.pipeline.settings import SECTIONS, PipelineSettings, ai_config
from mirae.pipeline.workers import SpeechWorker, VisionWorker
from mirae.robot import Robot
from mirae.vision.sources import build_camera

DEPENDENCIES = {
    "opencv": ("OpenCV", "cv2", ("opencv-python-headless", "opencv-python")),
    "cameras": ("Camera discovery", "cv2_enumerate_cameras", ("cv2-enumerate-cameras",)),
    "faces": ("face_recognition", "face_recognition", ("face-recognition",)),
    "whisper": ("faster-whisper", "faster_whisper", ("faster-whisper",)),
    "piper": ("Piper text-to-speech", "piper", ("piper-tts",)),
    "audio": ("Audio input", "sounddevice", ("sounddevice",)),
    "picamera2": ("Picamera2", "picamera2", ("picamera2",)),
    "gpio": ("GPIO", "gpiozero", ("gpiozero",)),
    "tof": ("VL53L1X", "VL53L1X", ("VL53L1X",)),
}


def dependencies(*, verify: bool = False) -> list[dict[str, Any]]:
    result = []
    for key, (name, module, packages) in DEPENDENCIES.items():
        installed = importlib.util.find_spec(module) is not None
        version = None
        for package in packages:
            try:
                version = importlib.metadata.version(package)
                break
            except importlib.metadata.PackageNotFoundError:
                pass
        error = None
        if installed and verify:
            try:
                importlib.import_module(module)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        result.append(
            {
                "id": key,
                "name": name,
                "installed": installed,
                "version": version,
                "import_checked": verify and installed,
                "error": error,
                "installable": key in PACKAGES,
            }
        )
    return result


class PipelineManager:
    def __init__(self, accounts: AuthStore, robot: Robot) -> None:
        self.settings = PipelineSettings(accounts)
        self.robot = robot
        self.change_lock = asyncio.Lock()
        self.check_slots = asyncio.Semaphore(2)
        self.runtime_connection_id = self.settings.value("active_connection")
        self.runtime_revision: float | None = None
        for row in self.settings.connections():
            if (
                row["id"] == self.runtime_connection_id
                and robot.config.ai.provider == "openai_compat"
            ):
                self.runtime_revision = row["updated_at"]
        self._dependencies = dependencies()
        self._camera_future: Future[dict[str, Any]] | None = None
        self._preview: bytes | None = None
        self._audio_future: Future[dict[str, Any]] | None = None
        self.jobs = JobRunner(accounts)
        self.models = ModelLibrary(accounts.path.parent / "models", self.jobs)
        self._devices: dict[str, Any] = {
            "cameras": {"items": [], "error": None, "checked_at": None},
            "audio": {"items": [], "error": None, "checked_at": None, "default": None},
        }

    def status(self) -> dict[str, Any]:
        cfg = self.robot.config
        desired = self.settings.desired_config(cfg)
        pending = [
            section for section in SECTIONS if getattr(desired, section) != getattr(cfg, section)
        ]
        physical = self.robot.hardware_connected
        drive = self.robot.last_drive
        sensor = self.robot._range_worker.latest()
        return {
            "host": socket.gethostname(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "dependencies": self._dependencies,
            "devices": self._devices,
            "models": self.models.listing(),
            "jobs": self.jobs.history(),
            "selected_connection": self.settings.value("active_connection"),
            "runtime_connection": self.runtime_connection_id,
            "runtime_connection_revision": self.runtime_revision,
            "runtime_llm": {
                "provider": cfg.ai.provider,
                "model": cfg.ai.model if self.robot.planner else None,
                "base_url": cfg.ai.base_url if cfg.ai.provider == "openai_compat" else None,
            },
            "pending_changes": pending,
            "pending_restart": [
                section for section in pending if section not in ("vision", "speech")
            ],
            "pending_local": [section for section in pending if section in ("vision", "speech")],
            "config": {
                section: getattr(desired, section).model_dump(mode="json") for section in SECTIONS
            },
            "active_config": {
                section: getattr(cfg, section).model_dump(mode="json") for section in SECTIONS
            },
            "local": {
                "vision": self.robot.vision.snapshot(),
                "speech": self.robot.speech.snapshot(),
            },
            "hardware": {
                "backend": cfg.hardware.backend,
                "physical": physical,
                "error": self.robot.hardware_error,
                "motors": {
                    "driver": type(self.robot.hardware.motors).__name__ if physical else None,
                    "output": {"left": drive.output.left, "right": drive.output.right}
                    if physical and drive
                    else None,
                },
                "encoders": {
                    "driver": type(self.robot.hardware.encoders).__name__ if physical else None,
                    "counts": list(drive.counts) if physical and drive else None,
                },
                "range": {
                    "driver": type(self.robot.hardware.range_sensor).__name__ if physical else None,
                    "distance_mm": drive.safety.range_mm if physical and drive else None,
                    "sample_age_s": max(0.0, self.robot.clock.now() - sensor.observed_at)
                    if physical and sensor
                    else None,
                },
                "video_devices": sorted(str(path) for path in Path("/dev").glob("video*"))
                if platform.system() == "Linux"
                else None,
            },
        }

    def schema(self) -> dict[str, Any]:
        return {
            section: getattr(self.robot.config, section).model_json_schema() for section in SECTIONS
        }

    def save_config(self, section: str, changes: dict[str, Any], actor: str) -> dict[str, Any]:
        if section not in SECTIONS:
            raise AccountError(404, "configuration section not found")
        desired = self.settings.desired_config(self.robot.config)
        data = desired.model_dump()
        previous = data[section]
        # Only one nested level is used by hardware pin and ToF configuration.
        merged = {
            **previous,
            **{
                key: (
                    {**previous[key], **value}
                    if isinstance(value, dict) and isinstance(previous.get(key), dict)
                    else value
                )
                for key, value in changes.items()
            },
        }
        data[section] = merged
        data["ai"] = desired.ai
        validated = MiraeConfig.model_validate(data)
        self.settings.set_value(section, getattr(validated, section).model_dump(mode="json"), actor)
        return {
            "saved": True,
            "restart_required": section not in ("vision", "speech")
            and getattr(validated, section) != getattr(self.robot.config, section),
            "apply_required": section in ("vision", "speech")
            and getattr(validated, section) != getattr(self.robot.config, section),
        }

    async def check_connection(self, connection_id: str) -> dict[str, Any]:
        if self.check_slots.locked():
            raise AccountError(429, "connection checks are busy")
        async with self.check_slots:
            connection, key, revision = await asyncio.to_thread(
                self.settings.connection_snapshot, connection_id
            )
            started = time.monotonic()
            result: dict[str, Any] = {
                "at": time.time(),
                "ok": False,
                "models": [],
                "http_status": None,
            }
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            try:
                async with (
                    asyncio.timeout(min(connection.timeout_s, 5.0)),
                    httpx.AsyncClient(
                        base_url=connection.base_url + "/",
                        headers=headers,
                        timeout=min(connection.timeout_s, 5.0),
                        trust_env=False,
                        follow_redirects=False,
                    ) as client,
                    client.stream("GET", "models") as response,
                ):
                    result["http_status"] = response.status_code
                    if response.status_code != 200:
                        result["error"] = f"Model listing returned HTTP {response.status_code}"
                    else:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > 1024 * 1024:
                                raise ValueError("model listing exceeds 1 MiB")
                            body.extend(chunk)
                        payload = json.loads(body)
                        ids = [item["id"] for item in payload["data"]]
                        if not all(isinstance(item, str) and len(item) <= 256 for item in ids):
                            raise ValueError("invalid model identifiers")
                        result.update(ok=True, models=sorted(set(ids)))
            except (TimeoutError, httpx.TimeoutException):
                result["error"] = "Connection timed out"
            except httpx.HTTPError:
                result["error"] = "Connection failed"
            except (ValueError, KeyError, TypeError):
                result["error"] = "Endpoint did not return a valid OpenAI-compatible model list"
            result["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
            if not await asyncio.to_thread(
                self.settings.save_check, connection_id, result, revision
            ):
                raise AccountError(409, "connection changed during the check; check it again")
            return result

    async def select_connection(self, connection_id: str | None, actor: str) -> None:
        async with self.change_lock:
            provider = None
            if connection_id is not None:
                check = await self.check_connection(connection_id)
                if not check["ok"]:
                    raise AccountError(422, check.get("error", "connection check failed"))
                connection, key = await asyncio.to_thread(self.settings.connection, connection_id)
                if not connection.model or connection.model not in check["models"]:
                    raise AccountError(422, "select a model returned by the connection check")
                cfg = ai_config(connection, key)
                provider = await asyncio.to_thread(build_provider, cfg)
            else:
                from mirae.config import AIConfig

                cfg = AIConfig(provider="none")
            try:
                self.robot.halt()
                await asyncio.to_thread(
                    self.settings.set_value, "active_connection", connection_id, actor
                )
            except BaseException:
                if provider:
                    await provider.aclose()
                raise
            self.robot.governor.invalidate_pending()
            old = self.robot._provider
            self.robot._provider = provider
            self.robot.planner = IntentPlanner(provider) if provider else None
            self.robot.config = self.robot.config.model_copy(update={"ai": cfg})
            self.runtime_connection_id = connection_id
            self.runtime_revision = next(
                (
                    row["updated_at"]
                    for row in await asyncio.to_thread(self.settings.connections)
                    if row["id"] == connection_id
                ),
                None,
            )
            if old:
                await old.aclose()

    def inspect_dependencies(self) -> list[dict[str, Any]]:
        importlib.invalidate_caches()
        self._dependencies = dependencies(verify=True)
        return self._dependencies

    def refresh_devices(self) -> dict[str, Any]:
        self._devices = {"cameras": camera_devices(), "audio": audio_devices()}
        return self._devices

    def install_dependency(self, dependency: str, actor: str) -> str:
        if dependency == "cameras":
            dependency = "opencv"
        if dependency not in PACKAGES:
            raise AccountError(422, "this package must be supplied by the operating system")
        if dependency in ("gpio", "tof") and platform.system() != "Linux":
            raise AccountError(422, "this hardware package requires Linux on the robot")
        if self.robot.vision.alive or self.robot.speech.alive:
            raise AccountError(409, "stop local processing before changing its Python packages")

        def install(job: str) -> dict[str, Any]:
            result = self.jobs.install(job, dependency)
            self.inspect_dependencies()
            self.refresh_devices()
            return result

        return self.jobs.start("install", dependency, actor, install)

    def download_model(self, model: str, actor: str) -> str:
        self.models.directory(model)
        return self.jobs.start(
            "download", model, actor, lambda job: self.models.download(job, model)
        )

    async def activate_model(self, model: str, actor: str) -> None:
        section, settings = self.models.settings(model)
        settings["enabled"] = True
        if section == "vision":
            cameras = (await asyncio.to_thread(self.refresh_devices))["cameras"]
            if not cameras["items"]:
                raise AccountError(422, cameras["error"] or "no camera connected")
            desired = self.settings.desired_config(self.robot.config).vision
            selected = next(
                (c for c in cameras["items"] if c["id"] == desired.camera_device),
                cameras["items"][0],
            )
            settings.update(source=selected["source"], camera_device=selected["id"])
        async with self.change_lock:
            await asyncio.to_thread(self.save_config, section, settings, actor)
        await self.apply_local(actor)

    async def set_local_enabled(self, section: str, enabled: bool, actor: str) -> None:
        if section not in ("vision", "speech"):
            raise AccountError(404, "unknown local processor")
        async with self.change_lock:
            changes: dict[str, Any] = {"enabled": enabled}
            if section == "vision" and enabled:
                desired = self.settings.desired_config(self.robot.config).vision
                if desired.source == "none":
                    changes["source"] = "opencv"
            await asyncio.to_thread(self.save_config, section, changes, actor)
        await self.apply_local(actor)

    async def apply_local(self, actor: str) -> None:
        async with self.change_lock:
            if (self._camera_future and not self._camera_future.done()) or (
                self._audio_future and not self._audio_future.done()
            ):
                raise AccountError(409, "device test is finishing; apply after the test completes")
            desired = await asyncio.to_thread(self.settings.desired_config, self.robot.config)
            self.robot.maintenance = True
            try:
                self.robot.halt()
                await asyncio.gather(
                    asyncio.to_thread(self.robot.vision.close),
                    asyncio.to_thread(self.robot.speech.close),
                )
                stopped_by = time.monotonic() + 30
                while self.robot.vision.alive or self.robot.speech.alive:
                    if time.monotonic() > stopped_by:
                        raise AccountError(504, "local processing has not released its devices yet")
                    await asyncio.sleep(0.1)
                vision, speech = VisionWorker(desired.vision), SpeechWorker(desired.speech)
                try:
                    vision.start()
                    speech.start()
                except BaseException:
                    await asyncio.gather(
                        asyncio.to_thread(vision.close), asyncio.to_thread(speech.close)
                    )
                    raise
                self.robot.vision, self.robot.speech = vision, speech
                self.robot.config = self.robot.config.model_copy(
                    update={"vision": desired.vision, "speech": desired.speech}
                )
                self.robot._perception_samples = {"vision": 0, "speech": 0}
                await asyncio.to_thread(
                    self.settings.set_value, "local_applied_at", time.time(), actor
                )
                deadline = time.monotonic() + 30
                while True:
                    waiting = False
                    for name, worker in (("vision", vision), ("speech", speech)):
                        snapshot = worker.snapshot()
                        if snapshot["state"] == "error":
                            raise AccountError(422, f"{name}: {snapshot['error']}")
                        waiting |= snapshot["state"] in ("starting", "not_started")
                    if not waiting:
                        break
                    if time.monotonic() > deadline:
                        raise AccountError(
                            504, "local processing is still starting; check its status"
                        )
                    await asyncio.sleep(0.1)
            finally:
                self.robot.maintenance = False

    async def capture_test(self) -> dict[str, Any]:
        if self._camera_future is not None and not self._camera_future.done():
            raise AccountError(409, "a camera capture is still finishing")
        future: Future[dict[str, Any]] = Future()
        self._camera_future = future

        def capture() -> None:
            try:
                future.set_result(self.check_camera())
            except BaseException as exc:
                future.set_exception(exc)

        threading.Thread(target=capture, name="camera-check", daemon=True).start()
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), timeout=3.0)
        except TimeoutError as exc:
            raise AccountError(
                504, "camera capture timed out; device cleanup awaits its read"
            ) from exc

    def check_camera(self) -> dict[str, Any]:
        deadline = time.monotonic() + 2
        while self.robot.vision.alive:
            current = self.robot.vision.snapshot()
            if current["state"] == "running" and self.robot.vision.frame():
                return {"ok": True, **current}
            if time.monotonic() > deadline:
                raise AccountError(
                    422, current.get("error") or "camera worker has not returned a frame yet"
                )
            time.sleep(0.05)
        desired = self.settings.desired_config(self.robot.config).vision
        if desired.source == "none":
            raise AccountError(422, "choose and save a camera source first")
        camera = build_camera(desired.model_copy(update={"enabled": True}))
        try:
            frame = camera.read()
            if frame is None:
                raise AccountError(422, "camera returned no frame")
            import cv2

            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                raise AccountError(422, "camera frame could not be encoded")
            self._preview = jpeg.tobytes()
            return {
                "ok": True,
                "device": getattr(camera, "device_name", None),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "captured_at": time.time(),
            }
        finally:
            camera.close()

    def camera_frame(self) -> bytes:
        frame = self.robot.vision.frame() if self.robot.vision.alive else self._preview
        if frame is None:
            raise AccountError(404, "capture a frame or start the camera first")
        return frame

    def live_vision(self) -> dict[str, Any]:
        snapshot, jpeg = self.robot.vision.live()
        return {
            **snapshot,
            "frame": base64.b64encode(jpeg).decode("ascii") if jpeg else None,
        }

    def live_speech(self, after: int) -> dict[str, Any]:
        entries = self.robot.speech.history(after)
        return {
            **self.robot.speech.snapshot(),
            "entries": entries,
            "cursor": entries[-1]["id"] if entries else after,
        }

    async def test_audio(self) -> dict[str, Any]:
        if self.robot.speech.alive:
            return {"ok": True, **self.robot.speech.snapshot()}
        if self._audio_future and not self._audio_future.done():
            raise AccountError(409, "microphone test is still finishing")
        future: Future[dict[str, Any]] = Future()
        self._audio_future = future

        def record() -> None:
            try:
                import numpy as np

                cfg = self.settings.desired_config(self.robot.config).speech
                with open_input(cfg.input_device) as (stream, info, rate):
                    block, overflowed = stream.read(rate * 2)
                pcm = np.frombuffer(bytes(block), dtype=np.int16).astype(np.float32) / 32768
                future.set_result(
                    {
                        "ok": True,
                        "device": info["name"],
                        "sample_rate": rate,
                        "peak": float(np.max(np.abs(pcm))),
                        "rms": float(np.sqrt(np.mean(pcm**2))),
                        "overflowed": bool(overflowed),
                        "captured_at": time.time(),
                    }
                )
            except BaseException as exc:
                future.set_exception(exc)

        threading.Thread(target=record, name="microphone-test", daemon=True).start()
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), 5)
        except TimeoutError as exc:
            raise AccountError(
                504, "microphone test timed out; waiting for device cleanup"
            ) from exc
