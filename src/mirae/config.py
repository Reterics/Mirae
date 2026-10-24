"""Typed configuration.

Resolution order (later wins):
  1. defaults in the models below
  2. the built-in profile, ``mirae/profiles/<profile>.toml``
  3. an optional user file (``--config`` or ``MIRAE_CONFIG``), e.g. /etc/mirae/mirae.toml
"""

from __future__ import annotations

import os
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Profile = Literal["sim", "pi"]


class MotorPins(BaseModel):
    """TB6612FNG wiring, BCM numbering. See docs/wiring.md."""

    stby: int = 4
    ain1: int = 5
    ain2: int = 6
    pwma: int = 12
    bin1: int = 23
    bin2: int = 24
    pwmb: int = 13


class EncoderPins(BaseModel):
    left_a: int = 17
    left_b: int = 27
    right_a: int = 22
    right_b: int = 25


class ToFConfig(BaseModel):
    i2c_bus: int = 1
    address: int = 0x29
    xshut_pin: int | None = 26
    poll_hz: float = 20.0


class HardwareConfig(BaseModel):
    backend: Literal["sim", "pi"] = "sim"
    motor_pins: MotorPins = Field(default_factory=MotorPins)
    encoder_pins: EncoderPins = Field(default_factory=EncoderPins)
    tof: ToFConfig = Field(default_factory=ToFConfig)
    invert_left: bool = False
    invert_right: bool = False


class DriveConfig(BaseModel):
    wheel_diameter_mm: float = 42.0
    # Wheel centre to wheel centre in the CAD model (cad/blender/build_mirae.py, track_mm).
    track_width_mm: float = 138.8
    # N20E-12-100 (100 RPM at 12 V): assumed 150:1 gearbox x 7 PPR encoder. Measure on the real
    # robot (turn a wheel 10 times, divide the count by 10) and override.
    encoder_counts_per_rev: float = 1050.0
    max_wheel_rpm: float = 100.0
    control_hz: float = 50.0


class SafetyConfig(BaseModel):
    max_speed: float = Field(0.6, ge=0.0, le=1.0)
    # Deadman: a command without an explicit duration expires after this long.
    command_timeout_s: float = 0.5
    # Upper bound on any command's requested duration.
    max_command_duration_s: float = 5.0
    stop_distance_mm: float = 120.0
    slow_distance_mm: float = 300.0
    # A range reading older than this counts as missing; forward motion is blocked.
    range_stale_s: float = 0.5
    # How fast a wheel's output may grow, in duty per second (None: no limit). Only the wheels
    # push, so a sudden full-duty start can lift the caster, worst when pulling away uphill.
    # Slowing down and stopping are never delayed. This limits the duty, not the acceleration
    # itself: the motors' stall torque is not published.
    ramp_per_s: float | None = Field(1.5, gt=0.0)


class ApiConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    telemetry_hz: float = 10.0


class AIConfig(BaseModel):
    provider: Literal["none", "fake", "openai_compat"] = "none"
    # Any OpenAI-compatible endpoint: Ollama, llama.cpp server, LM Studio, vLLM, ...
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    api_key_env: str | None = None
    timeout_s: float = 20.0


class VisionConfig(BaseModel):
    enabled: bool = False
    source: Literal["none", "picamera2", "opencv"] = "none"
    camera_index: int = 0
    width: int = 640
    height: int = 480
    detector: Literal["none", "onnx"] = "none"
    model_path: str | None = None


class SpeechConfig(BaseModel):
    enabled: bool = False
    stt: Literal["none", "faster_whisper"] = "none"
    stt_model: str = "base"
    tts: Literal["none", "piper"] = "none"
    tts_voice: str | None = None


class MiraeConfig(BaseModel):
    profile: Profile = "sim"
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    drive: DriveConfig = Field(default_factory=DriveConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    speech: SpeechConfig = Field(default_factory=SpeechConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(profile: Profile = "sim", path: str | Path | None = None) -> MiraeConfig:
    profile_file = resources.files("mirae.profiles").joinpath(f"{profile}.toml")
    data: dict[str, Any] = tomllib.loads(profile_file.read_text(encoding="utf-8"))
    data["profile"] = profile

    user_path = path or os.environ.get("MIRAE_CONFIG")
    if user_path:
        with open(user_path, "rb") as fh:
            data = _deep_merge(data, tomllib.load(fh))

    return MiraeConfig.model_validate(data)
