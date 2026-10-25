import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from mirae.config import HardwareConfig, load_config
from mirae.hardware.base import HardwareBundle
from mirae.hardware.pi import GpioEncoders, Tb6612Driver, build_pi
from mirae.robot import Robot


def test_bundle_closes_every_device_even_if_stop_fails() -> None:
    motors, encoders, sensor = Mock(), Mock(), Mock()
    motors.stop.side_effect = OSError("GPIO disconnected")
    with pytest.raises(OSError):
        HardwareBundle(motors, encoders, sensor).close()
    motors.close.assert_called_once()
    encoders.close.assert_called_once()
    sensor.close.assert_called_once()


def test_partial_pi_bundle_initialization_releases_open_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    motors, encoders = Mock(), Mock()
    monkeypatch.setattr("mirae.hardware.pi.Tb6612Driver", Mock(return_value=motors))
    monkeypatch.setattr("mirae.hardware.pi.GpioEncoders", Mock(return_value=encoders))
    monkeypatch.setattr("mirae.hardware.pi.Vl53l1xSensor", Mock(side_effect=OSError("I2C failed")))
    with pytest.raises(OSError, match="I2C"):
        build_pi(HardwareConfig())
    motors.close.assert_called_once()
    encoders.close.assert_called_once()


def test_partial_motor_startup_keeps_standby_low_and_releases_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    standby, left = Mock(), Mock()
    gpio = ModuleType("gpiozero")
    gpio.DigitalOutputDevice = Mock(return_value=standby)  # type: ignore[attr-defined]
    gpio.Motor = Mock(side_effect=[left, OSError("right motor failed")])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gpiozero", gpio)
    with pytest.raises(OSError, match="right motor"):
        Tb6612Driver(HardwareConfig())
    standby.on.assert_not_called()
    standby.close.assert_called_once()
    left.close.assert_called_once()


def test_partial_encoder_startup_releases_first_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    left = Mock()
    gpio = ModuleType("gpiozero")
    gpio.RotaryEncoder = Mock(side_effect=[left, OSError("right encoder failed")])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gpiozero", gpio)
    with pytest.raises(OSError, match="right encoder"):
        GpioEncoders(HardwareConfig())
    left.close.assert_called_once()


def test_robot_constructor_cleans_hardware_when_provider_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    motors, encoders, sensor = Mock(), Mock(), Mock()
    monkeypatch.setattr(
        "mirae.robot.build_provider", Mock(side_effect=ValueError("invalid provider"))
    )
    with pytest.raises(ValueError, match="invalid provider"):
        Robot(load_config("local"), hardware=HardwareBundle(motors, encoders, sensor))
    motors.close.assert_called_once()
    encoders.close.assert_called_once()
    sensor.close.assert_called_once()


def test_motor_stop_disables_standby_before_attempting_both_wheels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    standby, left, right = Mock(), Mock(), Mock()
    standby.off.side_effect = lambda: events.append("standby off")
    left.stop.side_effect = OSError("left motor failed")
    right.stop.side_effect = lambda: events.append("right stopped")
    gpio = ModuleType("gpiozero")
    gpio.DigitalOutputDevice = Mock(return_value=standby)  # type: ignore[attr-defined]
    gpio.Motor = Mock(side_effect=[left, right])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gpiozero", gpio)
    driver = Tb6612Driver(HardwareConfig())
    with pytest.raises(OSError, match="left motor"):
        driver.stop()
    assert events == ["standby off", "right stopped"]


def test_motor_stop_attempts_both_wheels_even_if_standby_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    standby, left, right = Mock(), Mock(), Mock()
    standby.off.side_effect = OSError("standby failed")
    gpio = ModuleType("gpiozero")
    gpio.DigitalOutputDevice = Mock(return_value=standby)  # type: ignore[attr-defined]
    gpio.Motor = Mock(side_effect=[left, right])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gpiozero", gpio)
    driver = Tb6612Driver(HardwareConfig())
    with pytest.raises(OSError, match="standby failed"):
        driver.stop()
    left.stop.assert_called_once()
    right.stop.assert_called_once()
