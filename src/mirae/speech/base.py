from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AudioClip:
    """Mono signed 16-bit little-endian PCM."""

    pcm: bytes
    sample_rate: int


class SpeechToText(Protocol):
    def transcribe(self, clip: AudioClip) -> str: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> AudioClip: ...


class NullSpeechToText:
    def transcribe(self, clip: AudioClip) -> str:
        return ""


class NullTextToSpeech:
    def synthesize(self, text: str) -> AudioClip:
        return AudioClip(pcm=b"", sample_rate=16000)
