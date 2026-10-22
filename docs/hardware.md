# Hardware

## Shopping list

Buy these separately:

- Raspberry Pi 5
- Passive cooling case for the Raspberry Pi 5
- VL53L1X Time-of-Flight sensor module

The rest of the parts, with supplier part numbers. Prices are net HUF as of October 2026 and will change.

| Part no. | Product | Description | Unit price | Qty | Total |
|---|---|---|---:|---:|---:|
| 100.428.86 | N20E-06-100 | Mini geared motor with encoder, 6 V DC, 100 RPM | 3 420 Ft | 2 | 6 840 Ft |
| 100.427.70 | N20-3PI-WHL | Wheel for N20 geared motor, 42 mm, 3PI miniQ | 850 Ft | 2 | 1 701 Ft |
| 100.479.92 | TB6612FNG-M | TB6612FNG dual DC motor driver module | 694 Ft | 1 | 694 Ft |
| 100.284.94 | 1000uF/10V LOW ESR | Electrolytic capacitor, 1000 µF, 10 V, low ESR | 123 Ft | 1 | 123 Ft |
| 100.357.20 | RC-40-20/MF | Ribbon jumper cable, 20 cm, 40-pin, male–female | 928 Ft | 1 | 928 Ft |
| 100.392.82 | RPI-RIB40-C | 40-pin ribbon cable for Raspberry Pi, 20 cm, coloured | 933 Ft | 1 | 933 Ft |
| 100.374.53 | RPI-TCOBBLER | T-cobbler breakout for Raspberry Pi, breadboard | 764 Ft | 1 | 764 Ft |
| 100.431.82 | INMP441-M | Omnidirectional I2S microphone module | 1 850 Ft | 1 | 1 850 Ft |
| 100.457.04 | MAX98357-M | Class-D I2S amplifier / DAC module, max. 3 W | 925 Ft | 1 | 925 Ft |
| 100.492.93 | 3525-SPKR-4R-3W | Speaker, 4 Ω, 3 W, 35 × 25 mm | 567 Ft | 1 | 567 Ft |
| 100.374.58 | 2 X 18650 W | Battery holder, 2 × 18650, wired, 2S1P | 488 Ft | 1 | 488 Ft |
| 100.510.20 | TP-INR18650-35HE | Li-ion cell, 18650, 3.6 V, 3400 mAh, 10 A | 1 055 Ft | 2 | 2 111 Ft |
| 100.468.18 | HX-2S-JH20 | BMS module, 2S, 7.4 V, 10 A, with balancing | 832 Ft | 1 | 832 Ft |
| 100.423.75 | MINI560-5V-5A | DC-DC step-down module, 5 V, 5 A | 552 Ft | 1 | 552 Ft |
| 100.523.43 | 2576-STDN-PSU-CVCC | DC-DC step-down, current-limited charger, 4–32 V → 1.25–30 V, 3 A | 904 Ft | 1 | 904 Ft |
| 100.467.80 | PD-5-20 | USB-PD/QC trigger module, USB-C, 5/9/12/15/20 V | 584 Ft | 1 | 584 Ft |
| 100.480.89 | XL4015-5A-M | DC-DC step-down, current-limited charger, 4–32 V → 1.25–30 V, 5 A | 881 Ft | 1 | 881 Ft |
| 100.516.66 | BCASTER-15-10K | Metal ball caster, Ø 15.875 mm, max. 10 kg | 903 Ft | 1 | 903 Ft |
| 100.488.80 | RPI-CM3-NOIR | Raspberry Pi Camera Module 3 NoIR, Sony IMX708, 12 MP | — | 1 | — |
| | | | | **Total** | **22 580 Ft** |

The total doesn't include the Raspberry Pi 5, its cooling case or the VL53L1X:
[hestore_20261022.xml](hestore_20261022.xml)

## Components by subsystem

| Subsystem | Component | Notes |
|---|---|---|
| Compute | Raspberry Pi 5 | In a passive aluminium cooling case |
| Drive | 2× N20 6 V 100 RPM geared motors with encoders | Differential drive |
| Drive | 2× 42 mm wheels, 1× metal ball caster | |
| Drive | TB6612FNG dual motor driver, 1000 µF low-ESR capacitor | |
| Distance | VL53L1X Time-of-Flight sensor | Short-range obstacle detection |
| Vision | Raspberry Pi Camera Module 3 NoIR | Sony IMX708, 12 MP, no IR filter |
| Audio in | INMP441 I2S MEMS microphone | |
| Audio out | MAX98357 I2S DAC / Class-D amplifier, 4 Ω / 3 W speaker | |
| Power | 2× 18650 Li-ion (2S), 2S BMS, 5 V / 5 A buck converter | Pi and logic supply |
| Charging | USB-C PD trigger, current-limited buck charger modules | |
| Wiring | 40-pin ribbon cables, T-cobbler | Prototyping |

## Main computer

The Raspberry Pi 5 handles camera processing, speech recognition, text-to-speech, behavior logic, sensor processing, motor control, communication with AI services and the local web/API interface.

## Drive system

The first version uses a differential-drive layout:

```text
            FRONT
       ┌───────────────┐
       │    CAMERA     │
       └───────────────┘
        O             O
     LEFT           RIGHT
     MOTOR          MOTOR
             ○
         BALL CASTER
```

Encoders enable speed control, distance estimation, PID control, straighter driving and basic odometry.

## Sensors

- **Camera Module 3 NoIR** — object and person detection, person tracking, visual navigation, future VLM experiments.
- **VL53L1X ToF** — short-range obstacle detection and collision avoidance. Future versions may use multiple ToF sensors or LiDAR.

## Audio

- **INMP441** — voice recording, wake-word detection, speech recognition, environmental audio.
- **MAX98357 + 4 Ω / 3 W speaker** — text-to-speech, sound effects, status feedback.

## Enclosure

A small, minimal cube-like body, roughly 120–150 mm wide, designed as modular parts rather than a single shell so individual components can change without redesigning the whole robot:

```text
┌─────────────────────┐
│      TOP COVER      │
├─────────────────────┤
│     PI 5 MODULE     │
├─────────┬───────────┤
│ MOTOR   │   MOTOR   │
│ MOUNT   │   MOUNT   │
└─────────┴───────────┘
```

It provides mounting points for the Pi 5 and its cooling case, camera, microphone, speaker, motor driver, both motors, wheels, ball caster, VL53L1X, wiring and a future battery system.

The enclosure is generated parametrically in Blender, driven through Blender MCP by an AI coding agent. See [`cad/README.md`](../cad/README.md) for the build pipeline and printable STLs.
