"""Speaks everything published on ``speech.say``: story episodes and say intents.

Synthesis and playback run in worker threads, never on the event loop. The last clip is
kept so the dashboard can play it back. Playback failure (no speaker) keeps the clip.
"""

from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
import wave
from collections.abc import Callable
from typing import Any

from mirae.config import SpeechConfig
from mirae.core.bus import EventBus, Topics
from mirae.speech.base import AudioClip, TextToSpeech
from mirae.speech.engines import build_tts

log = logging.getLogger(__name__)


class Speaker:
    def __init__(
        self,
        bus: EventBus,
        config: Callable[[], SpeechConfig],
        elevenlabs_key: Callable[[], str | None],
    ) -> None:
        self._bus = bus
        self._config = config
        self._key = elevenlabs_key
        self._engine: TextToSpeech | None = None
        self._engine_for: tuple[Any, ...] | None = None
        self._stop = threading.Event()
        self._queue: asyncio.Queue[str] | None = None
        self._lock = threading.Lock()
        self._clip: AudioClip | None = None
        self._clips = 0
        self._status: dict[str, Any] = {"state": "idle", "error": None, "clip": 0}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _update(self, **data: Any) -> None:
        with self._lock:
            self._status = {**self._status, **data}

    def stop(self) -> None:
        """Stop the current playback and drop anything queued. Later messages play normally."""
        self._stop.set()
        while self._queue is not None and not self._queue.empty():
            self._queue.get_nowait()

    def wav(self) -> bytes | None:
        with self._lock:
            clip = self._clip
        if clip is None or not clip.pcm:
            return None
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(clip.sample_rate)
            out.writeframes(clip.pcm)
        return buffer.getvalue()

    def _build(self, cfg: SpeechConfig) -> TextToSpeech:
        key = self._key() if cfg.tts == "elevenlabs" else None
        wanted = (cfg.tts, cfg.tts_voice, cfg.elevenlabs_voice_id, cfg.elevenlabs_model, key)
        if self._engine is None or self._engine_for != wanted:
            self._engine = build_tts(cfg, key)
            self._engine_for = wanted
        return self._engine

    async def run(self) -> None:
        async with self._bus.subscribe(Topics.SAY, maxsize=4) as queue:
            self._queue = queue
            try:
                while True:
                    await self.speak(await queue.get())
            finally:
                self._stop.set()

    async def speak(self, text: str) -> None:
        cfg = self._config()
        if cfg.tts == "none":
            self._update(state="off", error=None)
            return
        self._stop.clear()
        parts = _paragraphs(text)
        self._update(state="synthesizing", engine=cfg.tts, text=text[:200], error=None)
        started = time.monotonic()
        with self._lock:
            self._clips += 1
            clip_id = self._clips
        pcm = bytearray()
        pending: asyncio.Task[AudioClip] | None = None
        try:
            from mirae.pipeline.devices import play_pcm

            engine = await asyncio.to_thread(self._build, cfg)
            pending = asyncio.create_task(asyncio.to_thread(engine.synthesize, parts[0]))
            info: dict[str, Any] = {}
            for index in range(len(parts)):
                assert pending is not None  # set for every index below the last
                clip = await pending
                # Synthesize the next paragraph while this one plays.
                pending = (
                    asyncio.create_task(asyncio.to_thread(engine.synthesize, parts[index + 1]))
                    if index + 1 < len(parts)
                    else None
                )
                pcm.extend(clip.pcm)
                with self._lock:
                    self._clip = AudioClip(bytes(pcm), clip.sample_rate)
                if index == 0:
                    self._update(
                        state="speaking",
                        clip=clip_id,
                        synthesis_ms=round((time.monotonic() - started) * 1000),
                    )
                self._update(duration_s=round(len(pcm) / 2 / clip.sample_rate, 1))
                if self._stop.is_set():
                    break
                info = await asyncio.to_thread(
                    play_pcm, clip.pcm, clip.sample_rate, cfg.output_device, self._stop
                )
        except Exception as exc:
            log.exception("speech failed")
            self._update(state="error", error=f"{type(exc).__name__}: {exc}")
            return
        finally:
            if pending is not None:
                pending.cancel()
        self._update(state="idle", device=info.get("name"))


def _paragraphs(text: str, limit: int = 700) -> list[str]:
    """Paragraph groups of up to ``limit`` characters, so playback starts early."""
    parts: list[str] = []
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        if parts and len(parts[-1]) + len(paragraph) + 2 <= limit:
            parts[-1] += "\n\n" + paragraph
        else:
            parts.append(paragraph)
    return parts or [text]
