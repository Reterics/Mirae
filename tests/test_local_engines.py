"""Opt-in, real downloads and native inference; no camera, microphone or API key needed.

Run with MIRAE_TEST_MODELS=1 after installing the vision and speech extras.
"""

import os
import time
from functools import partial
from pathlib import Path

import pytest

from mirae.api.accounts import AuthStore
from mirae.config import VisionConfig
from mirae.pipeline.jobs import JobRunner
from mirae.pipeline.models import CATALOG, ModelLibrary
from mirae.speech.base import AudioClip
from mirae.speech.engines import FasterWhisperSTT, PiperTTS
from mirae.vision.detectors import OpenCVDetector

pytestmark = pytest.mark.skipif(
    os.environ.get("MIRAE_TEST_MODELS") != "1",
    reason="set MIRAE_TEST_MODELS=1 for real model downloads",
)


def test_verified_downloads_and_native_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import numpy as np
    import sounddevice  # noqa: F401 - verifies the native PortAudio library loads

    # Pin the voice used by this integration test just like the production catalog.
    monkeypatch.setitem(
        CATALOG,
        "test-piper-voice",
        {
            "base": "https://huggingface.co/rhasspy/piper-voices/resolve/"
            "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/low/",
            "files": [
                (
                    "en_US-lessac-low.onnx",
                    63201294,
                    "f7d01dde371555732c4c314111ac79672b1a5ce2fc19266ab42178fd8df7f375",
                    "sha256",
                ),
                (
                    "en_US-lessac-low.onnx.json",
                    4882,
                    "45754dfdebb3b8661c3fc564713772deec6e064feeb5b4e9594857dc7305193a",
                    "sha256",
                ),
            ],
        },
    )
    runner = JobRunner(AuthStore(str(tmp_path / "accounts.db")))
    library = ModelLibrary(tmp_path / "models", runner)
    for model in ("mobilenet-ssd", "whisper-tiny", "test-piper-voice"):
        job = runner.start("download", model, "integration", partial(library.download, model=model))
        deadline = time.monotonic() + 600
        while True:
            status = runner.snapshot(job)
            if status["state"] not in ("queued", "running"):
                assert status["state"] == "succeeded", status
                break
            assert time.monotonic() < deadline, status
            time.sleep(0.1)
        assert library.installed(model)

    _, settings = library.settings("mobilenet-ssd")
    detector = OpenCVDetector(VisionConfig(**settings))
    assert detector.detect(np.zeros((480, 640, 3), dtype=np.uint8)) == []

    tts = PiperTTS(str(library.directory("test-piper-voice") / "en_US-lessac-low.onnx"))
    clip = tts.synthesize("Hello. This is a test of the voice system.")
    assert clip.sample_rate > 0 and clip.pcm and any(clip.pcm)
    stt = FasterWhisperSTT(str(library.directory("whisper-tiny")), "en")
    transcript = stt.transcribe(clip)
    assert "hello" in transcript.lower(), transcript
    # macOS and other devices may only support capture at their native 48 kHz.
    assert stt.transcribe(AudioClip(bytes(48000 * 2), 48000)) == ""


def test_native_face_recognition() -> None:
    import numpy as np

    pytest.importorskip("face_recognition")
    from mirae.vision.detectors import FaceRecognizer

    recognizer = FaceRecognizer(VisionConfig(faces_enabled=True))
    assert recognizer.detect(np.zeros((480, 640, 3), dtype=np.uint8)) == []
