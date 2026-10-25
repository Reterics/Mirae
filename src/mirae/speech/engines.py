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
    """Local neural TTS. The voice is a downloaded .onnx file; nothing leaves the machine."""

    def __init__(self, voice: str | None) -> None:
        from piper import PiperVoice

        if not voice:
            raise ValueError("Piper needs a voice model file (speech.tts_voice)")
        self._voice = PiperVoice.load(voice)

    def synthesize(self, text: str) -> AudioClip:
        chunks = list(self._voice.synthesize(text))
        rate = chunks[0].sample_rate if chunks else 22050
        return AudioClip(b"".join(c.audio_int16_bytes for c in chunks), rate)


class ElevenLabsTTS:
    """Hosted TTS over HTTPS. Optional: the text is sent to ElevenLabs."""

    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    RATE = 24000

    def __init__(self, api_key: str | None, voice_id: str, model: str) -> None:
        import httpx

        if not api_key:
            raise ValueError("ElevenLabs needs an API key; set it in Speech settings")
        self._client = httpx.Client(headers={"xi-api-key": api_key}, timeout=120.0, trust_env=False)
        self._voice = voice_id
        self._model = model

    def synthesize(self, text: str) -> AudioClip:
        response = self._client.post(
            self.URL.format(voice=self._voice),
            params={"output_format": f"pcm_{self.RATE}"},
            json={"text": text, "model_id": self._model},
        )
        if response.status_code != 200:
            raise RuntimeError(f"ElevenLabs returned HTTP {response.status_code}: {response.text}")
        return AudioClip(response.content, self.RATE)


def build_stt(cfg: SpeechConfig) -> SpeechToText:
    if cfg.enabled and cfg.stt == "faster_whisper":
        return FasterWhisperSTT(cfg.stt_model, cfg.language)
    return NullSpeechToText()


def build_tts(cfg: SpeechConfig, elevenlabs_key: str | None = None) -> TextToSpeech:
    """Speaking is independent of ``enabled``, which only controls listening."""
    if cfg.tts == "piper":
        return PiperTTS(cfg.tts_voice)
    if cfg.tts == "elevenlabs":
        return ElevenLabsTTS(elevenlabs_key, cfg.elevenlabs_voice_id, cfg.elevenlabs_model)
    return NullTextToSpeech()
