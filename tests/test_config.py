from pathlib import Path

import pytest
from pydantic import ValidationError

from mirae.config import MiraeConfig, load_config


def test_profiles_load() -> None:
    local = load_config("local")
    assert local.hardware.backend == "none"
    assert local.ai.provider == "none"

    pi = load_config("pi")
    assert pi.hardware.backend == "pi"
    assert pi.api.host == "127.0.0.1"


def test_user_file_overrides_profile(tmp_path: Path) -> None:
    user = tmp_path / "mirae.toml"
    user.write_text("[safety]\nmax_speed = 0.4\n[hardware.motor_pins]\npwma = 18\n")
    cfg = load_config("pi", user)
    assert cfg.safety.max_speed == 0.4
    assert cfg.hardware.motor_pins.pwma == 18
    assert cfg.hardware.motor_pins.pwmb == 13
    assert cfg.hardware.backend == "pi"


def test_pi_module_imports_without_pi_libraries() -> None:
    # Importing must not touch gpiozero/VL53L1X; only constructing a driver does.
    import mirae.hardware.pi  # noqa: F401


@pytest.mark.parametrize(
    "data",
    [
        {"hardware": {"backend": "sim"}},
        {"ai": {"provider": "fake"}},
        {"saftey": {"max_speed": 0.1}},
        {"safety": {"max_speeed": 0.1}},
        {"drive": {"control_hz": 0}},
        {"drive": {"track_width_mm": -1}},
        {"drive": {"encoder_counts_per_rev": 0}},
        {"safety": {"range_stale_s": float("inf")}},
        {"safety": {"stop_distance_mm": float("nan")}},
        {"safety": {"stop_distance_mm": 400, "slow_distance_mm": 300}},
        {"safety": {"command_timeout_s": 6, "max_command_duration_s": 5}},
        {"safety": {"motor_watchdog_s": 0.01}},
        {"hardware": {"tof": {"poll_hz": 0}}},
        {"hardware": {"motor_pins": {"pwma": 17}}},
        {"hardware": {"tof": {"xshut_pin": 4}}},
        {"api": {"port": 0}},
        {"api": {"telemetry_hz": 0}},
    ],
)
def test_configuration_rejects_unsafe_values(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MiraeConfig.model_validate(data)


def test_face_recognition_does_not_require_object_detector() -> None:
    cfg = MiraeConfig.model_validate(
        {"vision": {"enabled": True, "source": "opencv", "detector": "none", "faces_enabled": True}}
    )
    assert cfg.vision.detector == "none"
    assert cfg.vision.faces_enabled


def test_configuration_is_immutable() -> None:
    config = MiraeConfig()
    with pytest.raises(ValidationError):
        config.safety.range_stale_s = float("inf")  # type: ignore[misc]
