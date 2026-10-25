import asyncio
import threading
from typing import Any

import pytest

from mirae.config import SpeechConfig
from mirae.core.bus import EventBus
from mirae.speech import speaker as speaker_module
from mirae.speech.base import AudioClip
from mirae.speech.speaker import Speaker, _paragraphs


class EchoTTS:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, text: str) -> AudioClip:
        self.texts.append(text)
        return AudioClip(b"\x01\x00" * len(text), 1000)


def test_paragraphs_group_up_to_the_limit() -> None:
    text = "a" * 400 + "\n\n" + "b" * 200 + "\n\n" + "c" * 400
    assert [len(p) for p in _paragraphs(text)] == [602, 400]
    assert _paragraphs("one line") == ["one line"]


def test_speaker_plays_each_paragraph_and_keeps_the_whole_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = EchoTTS()
    played: list[int] = []

    def play(pcm: bytes, rate: int, device: str | None, stop: threading.Event) -> dict[str, Any]:
        played.append(len(pcm))
        return {"name": "test speaker"}

    monkeypatch.setattr("mirae.pipeline.devices.play_pcm", play)
    monkeypatch.setattr(speaker_module, "build_tts", lambda cfg, key: engine)
    speaker = Speaker(EventBus(), lambda: SpeechConfig(tts="piper", tts_voice="x"), lambda: None)

    asyncio.run(speaker.speak("a" * 600 + "\n\n" + "b" * 600))

    assert engine.texts == ["a" * 600, "b" * 600]
    assert played == [1200, 1200]
    assert speaker.snapshot()["state"] == "idle"
    assert speaker.snapshot()["duration_s"] == 1.2
    wav = speaker.wav()
    assert wav is not None and len(wav) == 44 + 2400
