"""Camera backend selection and cleanup across supported operating systems."""

import sys
import types
from unittest.mock import Mock

import pytest

from mirae.config import VisionConfig
from mirae.pipeline.devices import camera_devices
from mirae.vision.sources import OpenCVCamera, Picamera2Camera


@pytest.mark.parametrize("system,backend", [("Windows", 700), ("Darwin", 1200), ("Linux", 0)])
def test_camera_enumeration_uses_native_backend(
    monkeypatch: pytest.MonkeyPatch, system: str, backend: int
) -> None:
    cv = types.ModuleType("cv2")
    cv.CAP_DSHOW = 700  # type: ignore[attr-defined]
    cv.CAP_AVFOUNDATION = 1200  # type: ignore[attr-defined]
    cv.CAP_ANY = 0  # type: ignore[attr-defined]
    enumeration = types.ModuleType("cv2_enumerate_cameras")
    enumerate_cameras = Mock(
        return_value=[
            types.SimpleNamespace(
                backend=backend, path="device-id", name="Physical camera", index=0
            )
        ]
    )
    enumeration.enumerate_cameras = enumerate_cameras  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cv2", cv)
    monkeypatch.setitem(sys.modules, "cv2_enumerate_cameras", enumeration)
    monkeypatch.setitem(sys.modules, "picamera2", None)
    monkeypatch.setattr("mirae.pipeline.devices.platform.system", lambda: system)
    found = camera_devices()
    enumerate_cameras.assert_called_once_with(backend)
    assert found["error"] is None
    assert found["items"][0]["id"] == f"opencv:{backend}:device-id"


def test_denied_camera_is_released_with_permission_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = Mock()
    cap.isOpened.return_value = False
    cv = types.ModuleType("cv2")
    cv.VideoCapture = Mock(return_value=cap)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cv2", cv)
    monkeypatch.setattr(
        "mirae.pipeline.devices.camera_devices",
        lambda: {
            "items": [
                {"source": "opencv", "id": "camera", "name": "Camera", "index": 0, "backend": 1200}
            ],
            "error": None,
        },
    )
    with pytest.raises(RuntimeError, match="Privacy & Security"):
        OpenCVCamera(VisionConfig())
    cap.release.assert_called_once()


def test_pi_camera_releases_device_when_start_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    camera = Mock()
    camera.start.side_effect = RuntimeError("camera busy")
    factory = Mock(return_value=camera)
    factory.global_camera_info.return_value = [{"Num": 0, "Model": "Camera Module 3"}]
    module = types.ModuleType("picamera2")
    module.Picamera2 = factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "picamera2", module)
    with pytest.raises(RuntimeError, match="camera busy"):
        Picamera2Camera(VisionConfig(source="picamera2"))
    camera.close.assert_called_once()
