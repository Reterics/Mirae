"""Optional perception workers own their devices and publish measured snapshots.

Workers never command motors or call an LLM. Audio remains local; transcripts
and detections are published to the runtime event bus for deterministic consumers.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Any

from mirae.config import SpeechConfig, VisionConfig
from mirae.pipeline.devices import open_input
from mirae.speech.base import AudioClip
from mirae.speech.engines import FasterWhisperSTT
from mirae.vision.base import Detector
from mirae.vision.detectors import FaceRecognizer, OpenCVDetector
from mirae.vision.sources import build_camera

log = logging.getLogger(__name__)


class LocalWorker:
    def __init__(self, name: str, enabled: bool) -> None:
        self._name = name
        self._enabled = enabled
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._data: dict[str, Any] = {
            "state": "disabled" if not enabled else "not_started",
            "last_sample_at": None,
            "samples": 0,
            "error": None,
        }

    def update(self, **data: Any) -> None:
        with self._lock:
            self._data = {**self._data, **data}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def start(self) -> None:
        if self._enabled:
            self.update(state="starting")
            self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                log.warning("%s is still finishing I/O or inference", self._name)

    def _run(self) -> None:
        try:
            self.run()
        except Exception as exc:
            self.update(state="error", error=f"{type(exc).__name__}: {exc}")
            log.exception("%s failed", self._name)
        finally:
            if self._stop.is_set():
                self.update(state="stopped")

    def run(self) -> None:
        raise NotImplementedError

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


class VisionWorker(LocalWorker):
    def __init__(self, cfg: VisionConfig) -> None:
        super().__init__("vision", cfg.enabled)
        self.cfg = cfg
        self._jpeg: bytes | None = None

    def frame(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def live(self) -> tuple[dict[str, Any], bytes | None]:
        """Snapshot and the JPEG its detections were measured on, read together."""
        with self._lock:
            return dict(self._data), self._jpeg

    def run(self) -> None:
        detectors: list[Detector] = []
        if self.cfg.detector == "opencv_dnn":
            detectors.append(OpenCVDetector(self.cfg))
        if self.cfg.faces_enabled:
            detectors.append(FaceRecognizer(self.cfg))
        camera = build_camera(self.cfg)
        count = 0
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                frame = camera.read()
                if frame is None:
                    raise RuntimeError("camera returned no frame")
                import cv2

                detections = [d for detector in detectors for d in detector.detect(frame)]
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                count += 1
                if self._stop.is_set():
                    break
                # Frame and detections are published together so overlays match the image.
                with self._lock:
                    if ok:
                        self._jpeg = encoded.tobytes()
                    self._data = {
                        **self._data,
                        "state": "running",
                        "last_sample_at": time.time(),
                        "samples": count,
                        "frame_width": int(frame.shape[1]),
                        "frame_height": int(frame.shape[0]),
                        "processing_ms": (time.monotonic() - started) * 1000,
                        "detections": [asdict(d) for d in detections],
                        "device": getattr(camera, "device_name", None),
                    }
                self._stop.wait(max(0.0, 1 / self.cfg.max_fps - (time.monotonic() - started)))
        finally:
            camera.close()


class SpeechWorker(LocalWorker):
    HISTORY = 50

    def __init__(self, cfg: SpeechConfig) -> None:
        super().__init__("speech", cfg.enabled and cfg.stt != "none")
        self.cfg = cfg
        self._history: deque[dict[str, Any]] = deque(maxlen=self.HISTORY)

    def history(self, after: int = 0) -> list[dict[str, Any]]:
        """Transcribed chunks with an ``id`` greater than ``after``, oldest first."""
        with self._lock:
            return [dict(entry) for entry in self._history if entry["id"] > after]

    def run(self) -> None:
        import numpy as np

        engine = FasterWhisperSTT(self.cfg.stt_model, self.cfg.language)
        count = 0
        blocks: queue.Queue[bytes] = queue.Queue(maxsize=max(8, round(self.cfg.chunk_s * 8)))
        dropped = 0

        def receive(data: Any, frames: int, timing: Any, status: Any) -> None:
            nonlocal dropped
            if self._stop.is_set():
                return
            if blocks.full():
                try:
                    blocks.get_nowait()
                    dropped += 1
                except queue.Empty:
                    pass
            try:
                blocks.put_nowait(bytes(data))
            except queue.Full:
                dropped += 1

        with open_input(self.cfg.input_device, callback=receive) as (_stream, info, rate):
            self.update(state="listening", device=info["name"], sample_rate=rate)
            while not self._stop.is_set():
                pcm = bytearray()
                while len(pcm) < round(self.cfg.chunk_s * rate) * 2:
                    if self._stop.is_set():
                        return
                    try:
                        pcm.extend(blocks.get(timeout=0.25))
                    except queue.Empty:
                        continue
                started = time.monotonic()
                text = engine.transcribe(AudioClip(bytes(pcm), rate))
                count += 1
                if self._stop.is_set():
                    return
                sample = {
                    "last_sample_at": time.time(),
                    "processing_ms": (time.monotonic() - started) * 1000,
                    "transcript": text,
                    "peak": float(
                        np.max(np.abs(np.frombuffer(pcm, dtype=np.int16).astype(np.float32)))
                    )
                    / 32768,
                }
                with self._lock:
                    self._history.append(
                        {
                            "id": count,
                            "at": sample["last_sample_at"],
                            "text": text,
                            "processing_ms": sample["processing_ms"],
                            "peak": sample["peak"],
                        }
                    )
                self.update(state="listening", samples=count, dropped_blocks=dropped, **sample)
