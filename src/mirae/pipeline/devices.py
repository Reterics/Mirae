"""Enumerate real OS camera and microphone devices, and open microphones safely."""

from __future__ import annotations

import platform
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

# PortAudio reads the device list once, when sounddevice is imported. A device that restarts or
# reconnects later (a wireless headset, a virtual mic such as SteelSeries Sonar) then fails to open
# from this long-running process with "Unanticipated host error ... [MME error 1]", while a fresh
# process opens it fine. Re-scanning (terminate + initialize) fixes that, but it also closes every
# open stream, so it only runs while none of ours are open.
_audio_lock = threading.Lock()
_open_inputs = 0


def _rescan_audio() -> None:
    """Re-read PortAudio's device list. Call with ``_audio_lock`` held and no stream open."""
    import sounddevice as sd

    sd._terminate()
    sd._initialize()


def _input_id(device: dict[str, Any], hosts: Any) -> str:
    """Stable microphone identity. List indexes shift when devices come and go; names don't."""
    return f"{hosts[device['hostapi']]['name']}:{device['name']}"


def _resolve_input(device_id: str | None) -> int | None:
    """PortAudio index for a saved microphone identity. None means the system default."""
    import sounddevice as sd

    if device_id is None:
        return None
    hosts = sd.query_hostapis()
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] > 0 and _input_id(device, hosts) == device_id:
            return index
    raise RuntimeError(
        f"Selected microphone ({device_id}) is no longer connected. Refresh the device list."
    )


@contextmanager
def open_input(
    device_id: str | None,
    *,
    callback: Callable[..., None] | None = None,
    block_s: float = 0.25,
) -> Iterator[tuple[Any, dict[str, Any], int]]:
    """Open a mono int16 microphone stream at 16 kHz, or the device's own rate if it refuses.

    Yields ``(stream, device_info, sample_rate)``. The stream is started and is closed on exit.
    """
    import sounddevice as sd

    global _open_inputs
    with _audio_lock:
        if _open_inputs == 0:
            _rescan_audio()
        device = _resolve_input(device_id)
        info = sd.query_devices(device, "input")
        rate = 16000
        try:
            sd.check_input_settings(device=device, channels=1, samplerate=rate, dtype="int16")
        except sd.PortAudioError:
            rate = int(info["default_samplerate"])
        stream = sd.RawInputStream(
            samplerate=rate,
            channels=1,
            dtype="int16",
            device=device,
            blocksize=round(rate * block_s),
            callback=callback,
        )
        _open_inputs += 1
    try:
        with stream:
            yield stream, info, rate
    finally:
        with _audio_lock:
            _open_inputs -= 1


def camera_devices() -> dict[str, Any]:
    try:
        import cv2
        from cv2_enumerate_cameras import enumerate_cameras

        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        cameras: list[dict[str, Any]] = [
            {
                "id": f"opencv:{c.backend}:{c.path or c.name}",
                "name": c.name,
                "index": c.index,
                "backend": c.backend,
                "path": c.path,
                "source": "opencv",
            }
            for c in enumerate_cameras(backend)
        ]
        # Prefer a physical device to a virtual camera for automatic selection.
        cameras.sort(key=lambda c: ("virtual" in c["name"].lower(), c["index"]))
        try:
            from picamera2 import Picamera2

            for item in Picamera2.global_camera_info():
                cameras.append(
                    {
                        "id": f"picamera2:0:{item['Num']}",
                        "name": item["Model"],
                        "index": item["Num"],
                        "backend": 0,
                        "path": item.get("Id", ""),
                        "source": "picamera2",
                    }
                )
        except ImportError:
            pass
        return {"items": cameras, "error": None, "checked_at": time.time()}
    except Exception as exc:
        return {"items": [], "error": f"{type(exc).__name__}: {exc}", "checked_at": time.time()}


def audio_devices() -> dict[str, Any]:
    try:
        import sounddevice as sd

        with _audio_lock:
            if _open_inputs == 0:
                _rescan_audio()
            devices = sd.query_devices()
            hosts = sd.query_hostapis()
            default = int(sd.query_devices(kind="input")["index"])
        inputs = [
            {
                "id": _input_id(d, hosts),
                "index": i,
                "name": d["name"],
                "host_api": hosts[d["hostapi"]]["name"],
                "channels": int(d["max_input_channels"]),
                "sample_rate": int(d["default_samplerate"]),
                "default": i == default,
            }
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
        inputs.sort(key=lambda d: (not d["default"], d["index"]))
        return {"items": inputs, "default": default, "error": None, "checked_at": time.time()}
    except Exception as exc:
        return {
            "items": [],
            "default": None,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at": time.time(),
        }
