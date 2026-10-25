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
    def __init__(self, model: str, language: str | None = None) -> None:
        from faster_whisper import WhisperModel

        # int8 on CPU is the practical setting for a Pi 5.
        self._model = WhisperModel(
            model, device="cpu", compute_type="int8", cpu_threads=2, local_files_only=True
        )
        self._language = language

    def transcribe(self, clip: AudioClip) -> str:
        import numpy as np

        if clip.sample_rate == 16000:
            audio = np.frombuffer(clip.pcm, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            import av

            frame = av.AudioFrame.from_ndarray(
                np.frombuffer(clip.pcm, dtype=np.int16).reshape(1, -1),
                format="s16",
                layout="mono",
            )
            frame.sample_rate = clip.sample_rate
            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
            frames = [*resampler.resample(frame), *resampler.resample(None)]
            audio = np.concatenate([f.to_ndarray().reshape(-1) for f in frames])
        segments, _info = self._model.transcribe(audio, vad_filter=True, language=self._language)
        return " ".join(segment.text.strip() for segment in segments)


class PiperTTS:
    def __init__(self, voice: str | None) -> None:
        # TODO(V0.4): load a Piper voice (.onnx + .json, downloaded into models/).
        raise NotImplementedError("Piper TTS is planned for V0.4")

    def synthesize(self, text: str) -> AudioClip:
        raise NotImplementedError


def build_stt(cfg: SpeechConfig) -> SpeechToText:
    if cfg.enabled and cfg.stt == "faster_whisper":
        return FasterWhisperSTT(cfg.stt_model, cfg.language)
    return NullSpeechToText()


def build_tts(cfg: SpeechConfig) -> TextToSpeech:
    if cfg.enabled and cfg.tts == "piper":
        return PiperTTS(cfg.tts_voice)
    return NullTextToSpeech()
