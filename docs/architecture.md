# Architecture

## Overview

```text
          ┌──────────────────────┐
Camera ──►│  Vision              │
Mic ─────►│  Speech Recognition  │
ToF ─────►│  Environment         │
          │  Behavior Engine     │
          │  AI / LLM            │
          └──────────┬───────────┘
                     │
                 Motor Driver
                  /        \
              Motor        Motor
```

## Software stack

- **OS:** Raspberry Pi OS 64-bit (Bookworm or Trixie)
- **Language:** Python 3.11+
- **API:** FastAPI
- **Hardware libraries:** `gpiozero` on `lgpio`, `smbus2`/`vl53l1x`, `picamera2`
- **Vision:** OpenCV and ONNX Runtime with lightweight object/person detection
- **Speech:** faster-whisper (STT), Piper (TTS)

Hardware-specific code stays isolated behind a hardware abstraction layer with a simulated backend, so the whole stack runs on Windows and macOS during development. Details, decisions and the dev workflow are in [software.md](software.md).

## Robot API

A local FastAPI service exposes movement commands, sensor state, camera information, robot status, AI actions, debugging and remote control.

```http
POST /api/movement
Content-Type: application/json

{ "action": "forward", "speed": 0.3 }
```

## Voice pipeline

```text
INMP441 → ALSA → Whisper → Intent / LLM → Behavior Engine ─┬─► Robot action
                                                           └─► TTS → MAX98357 → Speaker
```

Speech recognition can run locally on the Pi, on another machine on the LAN, or through a remote API, depending on available compute.

## Computer vision

Example person-following behavior:

```text
Camera → person detected → horizontal position
   ├── left     → turn left
   ├── centered → move forward
   └── right    → turn right
```

Future work: face detection, object tracking, gesture recognition, visual navigation, VLM integration.

## AI layer

The AI layer is provider-independent: Ollama, local open-weight models, external APIs, or a dedicated AI server on the LAN. The Pi does not need to run the largest models itself.

```text
┌────────────┐   Wi-Fi / LAN   ┌───────────────┐
│ Robot Pi 5 │ ──────────────► │ Ollama / LLM  │
│            │ ◄────────────── │ VLM / Whisper │
└────────────┘                 └───────────────┘
```

The robot keeps basic autonomous behavior if the AI backend is unavailable.

## Behavior engine

LLMs never drive GPIO pins or motors directly. They emit high-level intents, which the behavior engine turns into safe actions:

```json
{ "action": "approach_person", "speed": 0.25 }
```

```text
User → Speech → LLM → Intent → Behavior Engine → Navigation / Safety → Motor Controller
```

Behavior states: `IDLE`, `EXPLORE`, `FOLLOW`, `APPROACH`, `AVOID`, `LISTEN`, `SPEAK`, `SLEEP`.

This keeps AI decisions away from safety-critical, low-level motor control.

## Repository layout

```text
src/mirae/
├── core/       clock, event bus
├── hardware/   HAL interfaces, sim backend, Pi backend (motors, encoders, ToF)
├── safety/     safety governor, the only path to the motors
├── drive/      kinematics, odometry, drive controller
├── behavior/   intents, behavior engine and states
├── vision/     camera sources, detection
├── speech/     whisper, tts
├── ai/         LLM providers, intent planner
└── api/        FastAPI app
tests/
deploy/         Pi install script, systemd unit, boot config
cad/            printable STLs, print and assembly instructions
docs/           documentation
```
