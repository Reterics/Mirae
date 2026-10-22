# Wiring (Raspberry Pi 5)

Proposed pin map. Pin numbers are BCM GPIO numbers, and the software defaults in [`src/mirae/config.py`](../src/mirae/config.py) match this table. To change a pin, override it in `/etc/mirae/mirae.toml`; don't edit the code.

> ⚠️ Not yet verified on the robot. Check every connection against the module pinouts before powering up.

| Function | GPIO | Header pin | Module pin | Notes |
|---|---:|---:|---|---|
| I2C SDA | 2 | 3 | VL53L1X SDA | I2C1 |
| I2C SCL | 3 | 5 | VL53L1X SCL | I2C1 |
| Driver standby | 4 | 7 | TB6612 STBY | Low = motors off |
| Left dir 1 | 5 | 29 | TB6612 AIN1 | |
| Left dir 2 | 6 | 31 | TB6612 AIN2 | |
| Left PWM | 12 | 32 | TB6612 PWMA | Hardware-PWM capable |
| Right PWM | 13 | 33 | TB6612 PWMB | Hardware-PWM capable |
| Right dir 1 | 23 | 16 | TB6612 BIN1 | |
| Right dir 2 | 24 | 18 | TB6612 BIN2 | |
| Left encoder A | 17 | 11 | Motor L, C1 | 3.3 V logic only |
| Left encoder B | 27 | 13 | Motor L, C2 | |
| Right encoder A | 22 | 15 | Motor R, C1 | |
| Right encoder B | 25 | 22 | Motor R, C2 | |
| ToF shutdown | 26 | 37 | VL53L1X XSHUT | Allows several ToF sensors later |
| ToF interrupt | 16 | 36 | VL53L1X GPIO1 | Reserved, unused so far |
| I2S BCLK | 18 | 12 | INMP441 SCK, MAX98357 BCLK | Shared |
| I2S LRCLK | 19 | 35 | INMP441 WS, MAX98357 LRC | Shared |
| I2S data in | 20 | 38 | INMP441 SD | Mic → Pi |
| I2S data out | 21 | 40 | MAX98357 DIN | Pi → amp |

**Kept free:**

* GPIO 7–11 (SPI0), for a future faceplate display
* GPIO 14/15 (UART), for a serial console
* GPIO 0/1 (HAT ID EEPROM)

The faceplate LEDs aren't assigned yet.

**Power and logic levels:**

* The TB6612 VM pin takes the battery rail (2S, 6.0–8.4 V). The N20s are rated 6 V, so cap `safety.max_speed` until the motors have been checked at full battery voltage.
* VCC on the TB6612 and on the encoders is 3.3 V from the Pi.
* Put the 1000 µF capacitor across VM and GND, close to the driver.
* The INMP441 L/R pin goes to GND (left channel).
* The MAX98357 VIN is 5 V from the buck converter.
