"""Local speech engines, imported lazily. A LAN/remote STT backend can sit beside these."""

from __future__ import annotations

from mirae.config import SpeechConfig
from mirae.speech.base import (
    AudioClip,
    NullSpeechToText,
    NullTextToSpeech,
    SpeechToText,
    TextToSpeech,
)


class FasterWhisperSTT:
    def __init__(self, model: str) -> None:
        from faster_whisper import WhisperModel

        # int8 on CPU is the practical setting for a Pi 5.
        self._model = WhisperModel(model, device="cpu", compute_type="int8")

    def transcribe(self, clip: AudioClip) -> str:
        import numpy as np

        audio = np.frombuffer(clip.pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(audio, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments)


class PiperTTS:
    def __init__(self, voice: str | None) -> None:
        # TODO(V0.4): load a Piper voice (.onnx + .json, downloaded into models/).
        raise NotImplementedError("Piper TTS is planned for V0.4")

    def synthesize(self, text: str) -> AudioClip:
        raise NotImplementedError


def build_stt(cfg: SpeechConfig) -> SpeechToText:
    if cfg.enabled and cfg.stt == "faster_whisper":
        return FasterWhisperSTT(cfg.stt_model)
    return NullSpeechToText()


def build_tts(cfg: SpeechConfig) -> TextToSpeech:
    if cfg.enabled and cfg.tts == "piper":
        return PiperTTS(cfg.tts_voice)
    return NullTextToSpeech()
