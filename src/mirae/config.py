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
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Profile = Literal["local", "pi"]
Positive = Annotated[float, Field(gt=0.0)]
Pin = Annotated[int, Field(ge=0, le=27)]


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, validate_default=True, frozen=True
    )


class MotorPins(ConfigModel):
    """TB6612FNG wiring, BCM numbering. See docs/wiring.md."""

    stby: Pin = 4
    ain1: Pin = 5
    ain2: Pin = 6
    pwma: Pin = 12
    bin1: Pin = 23
    bin2: Pin = 24
    pwmb: Pin = 13


class EncoderPins(ConfigModel):
    left_a: Pin = 17
    left_b: Pin = 27
    right_a: Pin = 22
    right_b: Pin = 25


class ToFConfig(ConfigModel):
    i2c_bus: int = Field(1, ge=0)
    address: int = Field(0x29, ge=0x08, le=0x77)
    xshut_pin: Pin | None = 26
    poll_hz: Positive = 20.0
    read_timeout_s: Positive = 0.5


class HardwareConfig(ConfigModel):
    backend: Literal["none", "pi"] = "none"
    motor_pins: MotorPins = Field(default_factory=MotorPins)
    encoder_pins: EncoderPins = Field(default_factory=EncoderPins)
    tof: ToFConfig = Field(default_factory=ToFConfig)
    invert_left: bool = False
    invert_right: bool = False

    @model_validator(mode="after")
    def distinct_pins(self) -> Self:
        pins = [*self.motor_pins.model_dump().values(), *self.encoder_pins.model_dump().values()]
        if self.tof.xshut_pin is not None:
            pins.append(self.tof.xshut_pin)
        if len(pins) != len(set(pins)):
            raise ValueError("motor, encoder and ToF GPIO pins must be distinct")
        return self


class DriveConfig(ConfigModel):
    wheel_diameter_mm: Positive = 42.0
    # Wheel centre to wheel centre in the CAD model (cad/blender/build_mirae.py, track_mm).
    track_width_mm: Positive = 138.8
    # N20E-12-100 (100 RPM at 12 V): assumed 150:1 gearbox x 7 PPR encoder. Measure on the real
    # robot (turn a wheel 10 times, divide the count by 10) and override.
    encoder_counts_per_rev: Positive = 1050.0
    max_wheel_rpm: Positive = 100.0
    control_hz: Positive = 50.0


class SafetyConfig(ConfigModel):
    max_speed: float = Field(0.6, ge=0.0, le=1.0)
    # Deadman: a command without an explicit duration expires after this long.
    command_timeout_s: Positive = 0.5
    # Upper bound on any command's requested duration.
    max_command_duration_s: Positive = 5.0
    stop_distance_mm: Positive = 120.0
    slow_distance_mm: Positive = 300.0
    # A range reading older than this counts as missing; forward motion is blocked.
    range_stale_s: Positive = 0.5
    motor_watchdog_s: Positive = 0.2
    # How fast a wheel's output may grow, in duty per second (None: no limit). Only the wheels
    # push, so a sudden full-duty start can lift the caster, worst when pulling away uphill.
    # Slowing down and stopping are never delayed. This limits the duty, not the acceleration
    # itself: the motors' stall torque is not published.
    ramp_per_s: float | None = Field(1.5, gt=0.0)

    @model_validator(mode="after")
    def ordered_limits(self) -> Self:
        if self.slow_distance_mm <= self.stop_distance_mm:
            raise ValueError("slow_distance_mm must exceed stop_distance_mm")
        if self.command_timeout_s > self.max_command_duration_s:
            raise ValueError("command_timeout_s must not exceed max_command_duration_s")
        return self


class ApiConfig(ConfigModel):
    host: str = Field("127.0.0.1", min_length=1)
    port: int = Field(8000, ge=1, le=65535)
    telemetry_hz: Positive = 10.0
    database_path: str = Field("var/mirae.sqlite3", min_length=1)
    session_hours: Positive = Field(12.0, le=168.0)
    cookie_secure: bool = False


class AIConfig(ConfigModel):
    provider: Literal["none", "openai_compat"] = "none"
    # Any OpenAI-compatible endpoint: Ollama, llama.cpp server, LM Studio, vLLM, ...
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    api_key_env: str | None = None
    api_key: SecretStr | None = Field(None, repr=False, exclude=True)
    timeout_s: Positive = 20.0
    command_ttl_s: Positive = 5.0
    # Bedtime story episodes are long generations; a 3B model on a Pi 5 needs minutes.
    story_timeout_s: float = Field(300.0, gt=0.0, le=900.0)
    story_words: int = Field(350, ge=100, le=1000)


class VisionConfig(ConfigModel):
    enabled: bool = False
    source: Literal["none", "picamera2", "opencv"] = "opencv"
    camera_device: str | None = Field(
        None, description="Discovered camera identity; null selects the first physical camera."
    )
    camera_index: int = 0
    width: int = Field(640, gt=0, le=4096)
    height: int = Field(480, gt=0, le=4096)
    detector: Literal["none", "opencv_dnn"] = "none"
    model_path: str | None = Field(None, description="Local OpenCV-compatible SSD model file.")
    model_config_path: str | None = None
    labels_path: str | None = None
    input_width: int = Field(300, ge=32, le=4096)
    input_height: int = Field(300, ge=32, le=4096)
    input_scale: Positive = 1.0 / 127.5
    input_mean: tuple[float, float, float] = (127.5, 127.5, 127.5)
    swap_rb: bool = True
    confidence_threshold: float = Field(0.5, gt=0.0, le=1.0)
    faces_enabled: bool = False
    known_faces_path: str | None = Field(
        None,
        description="Local NPZ file with encodings (Nx128) and names arrays; pickle is disabled.",
    )
    face_tolerance: float = Field(0.5, gt=0.0, le=1.0)
    max_fps: float = Field(5.0, gt=0.0, le=30.0)

    @model_validator(mode="after")
    def camera_required(self) -> Self:
        if self.enabled and self.source == "none":
            raise ValueError("choose a camera source before enabling vision")
        if self.enabled and self.detector == "opencv_dnn" and not self.model_path:
            raise ValueError("OpenCV DNN requires a model file")
        return self


class SpeechConfig(ConfigModel):
    enabled: bool = False
    stt: Literal["none", "faster_whisper"] = "faster_whisper"
    stt_model: str = Field(
        "base",
        min_length=1,
        description="Local model path or cached model ID. Automatic downloads are disabled.",
    )
    tts: Literal["none", "piper", "elevenlabs"] = Field(
        "none", description="Speaks story episodes and say intents. Piper runs locally."
    )
    tts_voice: str | None = Field(
        None, min_length=1, description="Piper voice model (.onnx, with its .onnx.json beside it)."
    )
    elevenlabs_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", pattern=r"^[A-Za-z0-9]{8,40}$")
    elevenlabs_model: str = Field("eleven_v4", pattern=r"^[a-z0-9_]{3,40}$")
    output_device: str | None = Field(
        None,
        min_length=1,
        description='Speaker identity ("<host API>:<name>"); null selects the system default.',
    )
    input_device: str | None = Field(
        None,
        min_length=1,
        description='Discovered microphone identity ("<host API>:<name>"); null selects the '
        "system default input.",
    )
    chunk_s: float = Field(4.0, ge=1.0, le=15.0)
    language: str | None = Field(None, pattern=r"^[a-z]{2,3}$")

    @field_validator("input_device", mode="before")
    @classmethod
    def drop_device_index(cls, value: object) -> object:
        # Older settings stored a PortAudio list index, which points at a different device
        # whenever the list changes. It can't be mapped back to a device, so it resets to the
        # system default; pick the microphone again in the admin UI.
        return None if isinstance(value, int) else value


class MiraeConfig(ConfigModel):
    profile: Profile = "local"
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    drive: DriveConfig = Field(default_factory=DriveConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    speech: SpeechConfig = Field(default_factory=SpeechConfig)

    @model_validator(mode="after")
    def watchdog_budget(self) -> Self:
        if self.safety.motor_watchdog_s <= 2.0 / self.drive.control_hz:
            raise ValueError("motor_watchdog_s must allow more than two control periods")
        return self


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(profile: Profile = "local", path: str | Path | None = None) -> MiraeConfig:
    profile_file = resources.files("mirae.profiles").joinpath(f"{profile}.toml")
    data: dict[str, Any] = tomllib.loads(profile_file.read_text(encoding="utf-8"))
    data["profile"] = profile

    user_path = path or os.environ.get("MIRAE_CONFIG")
    if user_path:
        with open(user_path, "rb") as fh:
            data = _deep_merge(data, tomllib.load(fh))

    return MiraeConfig.model_validate(data)
