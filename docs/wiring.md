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

* Power chain: 4 × 18650 (2S2P, 6.0–8.4 V) → HX-2S-JH20 BMS → SZ-08CV set to 5.1 V for the Pi 5 and logic, and XL6009-UD set to 12.0 V for the motors. USB-C 5 V → USBC-2S-LI-BOOST charges the pack through the BMS. Set both converter outputs with a multimeter before connecting any load.
* The SL 19123 slide switch is the main power switch: it sits in series with the BMS P+ load output, before the SZ-08CV and XL6009-UD branches. Charging stays connected directly to the BMS and isn't switched.
* The TB6612 VM pin takes the 12.0 V motor rail from the XL6009-UD, which matches the N20E-12-100s' 12 V rating and stays under the TB6612's 13.5 V VM limit. The XL6009-UD steps up from the 6.0–8.4 V pack.
* VCC on the TB6612 and on the encoders is 3.3 V from the Pi.
* Put the 1000 µF / 16 V capacitor across VM and GND, close to the driver. A 10 V part must not go on this rail.
* The INMP441 L/R pin goes to GND (left channel).
* The MAX98357 VIN is the 5.1 V rail from the SZ-08CV.
* Current returns to the converter that supplies it. Motor current runs XL6009-UD OUT+ → TB6612 VM → motors → TB6612 GND → XL6009-UD OUT−, never through a Pi GND pin. The amplifier returns to the SZ-08CV the same way. The two converters' IN− terminals meet at BMS P−, the one common ground point.

**Power, ground and motor connections:**

Every module pin that isn't on a GPIO. Rails: `3V3` is the Pi's 3.3 V output (header pins 1 and 17, the same rail inside the Pi), `5V1` the SZ-08CV output, `12V0` the XL6009-UD output, and `GND` the common ground. "Wire goes to" is the exact point each wire lands on. A splice is where several wires are joined into one (soldered Y-joint, small perfboard or terminal block); a converter terminal may take several wires. Module pin names are the ones printed on each board; on the N20E's 6-wire cable, C1 and C2 are the encoder's phase A and phase B wires.

| Module pin | Connects to | Wire goes to | Notes |
|---|---|---|---|
| SZ-08CV VIN+ | BMS P+ | SL 19123 switch | Switched |
| SZ-08CV VIN− | GND | BMS P− | Common ground point. VIN− and Vout− are not bridged outside the board: there is a current-sense shunt between them |
| SZ-08CV Vout+ | 5V1 | Pi header pins 2 and 4 | The Pi 5 is powered through its header, not its USB-C port. MAX98357 Vin and the AI HAT+ 2 also wire to this terminal |
| SZ-08CV Vout− | GND | Pi header pins 6 and 9 | MAX98357 GND and the AI HAT+ 2 also wire to this terminal |
| XL6009-UD IN+ | BMS P+ | SL 19123 switch | Switched |
| XL6009-UD IN− | GND | BMS P− | |
| XL6009-UD OUT+ | 12V0 | TB6612 VM | And the capacitor + |
| XL6009-UD OUT− | GND | TB6612 GND | And the capacitor − |
| XL6009-UD EN | not connected | | Left open, the output stays on |
| TB6612 VCC | 3V3 | splice "3V3 drive" (Pi header pin 17) | Logic supply |
| TB6612 VM | 12V0 | XL6009-UD OUT+ | Motor supply |
| TB6612 GND | GND | XL6009-UD OUT− | All three GND pins. Never to a Pi GND pin |
| Capacitor + | 12V0 | TB6612 VM | 1000 µF / 16 V, across VM and GND at the driver |
| Capacitor − | GND | TB6612 GND | The driver's motor-side GND, beside VM |
| TB6612 AO1 | Motor L, Motor+ | Motor L, Motor+ | Left motor on channel A |
| TB6612 AO2 | Motor L, Motor− | Motor L, Motor− | |
| TB6612 BO1 | Motor R, Motor+ | Motor R, Motor+ | Right motor on channel B |
| TB6612 BO2 | Motor R, Motor− | Motor R, Motor− | |
| Motor L, Encoder+ | 3V3 | splice "3V3 drive" (Pi header pin 17) | Keeps C1/C2 at 3.3 V logic |
| Motor L, GND | GND | Pi header pin 30 | |
| Motor R, Encoder+ | 3V3 | splice "3V3 drive" (Pi header pin 17) | |
| Motor R, GND | GND | Pi header pin 34 | |
| VL53L1X VIN | 3V3 | splice "3V3 sensor" (Pi header pin 1) | Same as the Pi's logic level |
| VL53L1X GND | GND | Pi header pin 14 | |
| INMP441 VDD | 3V3 | splice "3V3 sensor" (Pi header pin 1) | Never 5 V: the INMP441 is a 3.3 V part |
| INMP441 GND | GND | Pi header pin 20 | |
| INMP441 L/R | GND | Pi header pin 25 | Left channel |
| MAX98357 Vin | 5V1 | SZ-08CV Vout+ | |
| MAX98357 GND | GND | SZ-08CV Vout− | Not a Pi GND pin: the amplifier's current returns to the converter |
| MAX98357 GAIN | not connected | | Default gain |
| MAX98357 SD | not connected | | Amplifier on |
| MAX98357 + | Speaker + | Speaker + | The 2-pin screw terminal |
| MAX98357 − | Speaker − | Speaker − | |
| AI HAT+ 2 5V | 5V1 | SZ-08CV Vout+ | Optional; the HAT's header pin 2 or 4 |
| AI HAT+ 2 GND | GND | SZ-08CV Vout− | Optional; the HAT's header pin 6 |

Pi header pin 39 (GND) stays free as a spare.

* I2S BCLK (header pin 12) and I2S LRCLK (header pin 35) each feed two modules. Each is one wire from the header to a splice near the Raspberry Pi GPIO breakout, before the harness splits, then one wire from the splice to each module.

* Optional AI HAT+ 2: it sits under the Pi, not on its header. It connects to the Pi only through the PCIe ribbon; its 5 V and GND come from the SZ-08CV terminals (table above), because the Pi's two 5 V pins already take the SZ-08CV feed. The ID EEPROM pins aren't connected, so if the HAT isn't detected, enable PCIe with `dtparam=pciex1` in `/boot/firmware/config.txt`.
