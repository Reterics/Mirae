"""Concrete camera sources, imported lazily.

* ``picamera2``: Camera Module 3 on the Pi (apt: python3-picamera2).
* ``opencv``: any webcam on Windows/macOS/Linux for development.
"""

from __future__ import annotations

from typing import Any

from mirae.config import VisionConfig
from mirae.vision.base import CameraSource, NullCamera


class OpenCVCamera:
    def __init__(self, cfg: VisionConfig) -> None:
        import cv2

        from mirae.pipeline.devices import camera_devices

        found = camera_devices()
        items = [item for item in found["items"] if item["source"] == "opencv"]
        selected = (
            next((item for item in items if item["id"] == cfg.camera_device), None)
            if cfg.camera_device
            else next(iter(items), None)
        )
        if selected is None:
            raise RuntimeError(
                found["error"] or "Selected camera is no longer connected. Refresh the device list."
            )
        self.device_name = selected["name"]
        self._cap = cv2.VideoCapture(selected["index"], selected["backend"])
        if not self._cap.isOpened():
            self._cap.release()
            raise RuntimeError("configured camera could not be opened")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)

    def read(self) -> Any | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()


class Picamera2Camera:
    def __init__(self, cfg: VisionConfig) -> None:
        from picamera2 import Picamera2

        available = Picamera2.global_camera_info()
        if not available:
            raise RuntimeError("No Raspberry Pi camera detected")
        index = (
            int(cfg.camera_device.rsplit(":", 1)[-1]) if cfg.camera_device else available[0]["Num"]
        )
        self.device_name = next((c["Model"] for c in available if c["Num"] == index), "Pi camera")
        self._cam = Picamera2(index)
        config = self._cam.create_video_configuration(
            main={"size": (cfg.width, cfg.height), "format": "BGR888"}
        )
        self._cam.configure(config)
        self._cam.start()

    def read(self) -> Any | None:
        return self._cam.capture_array()

    def close(self) -> None:
        self._cam.stop()
        self._cam.close()


def build_camera(cfg: VisionConfig) -> CameraSource:
    if not cfg.enabled or cfg.source == "none":
        return NullCamera()
    if cfg.source == "picamera2":
        return Picamera2Camera(cfg)
    return OpenCVCamera(cfg)
