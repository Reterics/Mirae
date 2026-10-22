from pathlib import Path

from mirae.config import load_config


def test_profiles_load() -> None:
    sim = load_config("sim")
    assert sim.hardware.backend == "sim"
    assert sim.ai.provider == "fake"

    pi = load_config("pi")
    assert pi.hardware.backend == "pi"
    assert pi.api.host == "0.0.0.0"


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
