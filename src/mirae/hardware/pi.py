"""Raspberry Pi 5 drivers. Only imported when ``hardware.backend = "pi"``.

The Pi 5 routes GPIO through the RP1 chip, so RPi.GPIO does not work; gpiozero
runs on its lgpio pin factory (python3-lgpio from apt).

Untested on hardware so far: verify each driver against docs/wiring.md.
"""

from __future__ import annotations

from typing import Any

from mirae.config import HardwareConfig
from mirae.hardware.base import HardwareBundle


class Tb6612Driver:
    """TB6612FNG: IN1/IN2 set direction, PWM sets duty, STBY enables the chip.

    PWM is software-timed by lgpio. If it proves too jittery, swap in hardware
    PWM on GPIO12/13 (see deploy/pi/config.txt.snippet) behind this same class.
    """

    def __init__(self, cfg: HardwareConfig) -> None:
        from gpiozero import DigitalOutputDevice, Motor

        pins = cfg.motor_pins
        self._invert = (-1.0 if cfg.invert_left else 1.0, -1.0 if cfg.invert_right else 1.0)
        self._stby = DigitalOutputDevice(pins.stby, initial_value=False)
        self._left = Motor(forward=pins.ain1, backward=pins.ain2, enable=pins.pwma, pwm=True)
        self._right = Motor(forward=pins.bin1, backward=pins.bin2, enable=pins.pwmb, pwm=True)
        self._stby.on()

    def set_speeds(self, left: float, right: float) -> None:
        self._left.value = max(-1.0, min(1.0, left * self._invert[0]))
        self._right.value = max(-1.0, min(1.0, right * self._invert[1]))

    def stop(self) -> None:
        self._left.stop()
        self._right.stop()

    def close(self) -> None:
        self.stop()
        self._stby.off()
        for device in (self._left, self._right, self._stby):
            device.close()


class GpioEncoders:
    """Quadrature decoding in Python via gpiozero edge callbacks.

    Known risk: at full speed the N20 encoders produce a few kHz of edges per
    wheel, which is near the limit of Python callbacks. If counts drift, move
    counting to the RP1/a microcontroller without changing this interface.
    """

    def __init__(self, cfg: HardwareConfig) -> None:
        from gpiozero import RotaryEncoder

        pins = cfg.encoder_pins
        self._sign = (-1 if cfg.invert_left else 1, -1 if cfg.invert_right else 1)
        self._left = RotaryEncoder(pins.left_a, pins.left_b, max_steps=0)
        self._right = RotaryEncoder(pins.right_a, pins.right_b, max_steps=0)

    def read_counts(self) -> tuple[int, int]:
        return self._left.steps * self._sign[0], self._right.steps * self._sign[1]

    def close(self) -> None:
        self._left.close()
        self._right.close()


class Vl53l1xSensor:
    def __init__(self, cfg: HardwareConfig) -> None:
        import VL53L1X
        from gpiozero import DigitalOutputDevice

        tof = cfg.tof
        self._xshut: Any = None
        if tof.xshut_pin is not None:
            self._xshut = DigitalOutputDevice(tof.xshut_pin, initial_value=True)
        self._dev = VL53L1X.VL53L1X(i2c_bus=tof.i2c_bus, i2c_address=tof.address)
        self._dev.open()
        self._dev.start_ranging(1)  # 1 = short range, up to ~1.3 m, best in ambient light

    def read_mm(self) -> float | None:
        distance = self._dev.get_distance()
        return float(distance) if distance > 0 else None

    def close(self) -> None:
        self._dev.stop_ranging()
        self._dev.close()
        if self._xshut is not None:
            self._xshut.close()


def build_pi(cfg: HardwareConfig) -> HardwareBundle:
    return HardwareBundle(
        motors=Tb6612Driver(cfg),
        encoders=GpioEncoders(cfg),
        range_sensor=Vl53l1xSensor(cfg),
    )
