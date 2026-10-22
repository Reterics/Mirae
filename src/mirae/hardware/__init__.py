"""Hardware abstraction layer.

Everything above this package talks to the interfaces in ``base``. The ``sim``
backend runs anywhere; the ``pi`` backend imports Pi-only libraries lazily, so
nothing outside a Pi ever imports gpiozero, lgpio, smbus2 or picamera2.
"""
