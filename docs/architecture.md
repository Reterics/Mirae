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

Hardware-specific code stays isolated behind a hardware abstraction layer. The default `local` profile runs administration and configured local processing without a robot backend. The `pi` profile initializes physical drivers. Missing hardware never supplies synthetic readings, and motion is rejected until physical hardware is initialized. Simulation helpers are used only by explicitly injected test fixtures. Details, decisions and the dev workflow are in [software.md](software.md).

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

## Runtime safety and access

All motor commands pass through the safety governor and a dedicated watchdog thread. Hard obstacle limits are applied after ramping as well. The watchdog enforces command expiry independently of asyncio and cuts output after a missing control heartbeat. It is a software fallback; a physical heartbeat cutoff/e-stop is still required for unattended operation.

A dedicated sensor thread owns ToF reads and cleanup, so cancellation cannot close an active read. A failed/stalled runtime loop stops motion, shuts down the API and exits with an error for systemd to restart. Health and telemetry report actual progress, faults and control-loop timing.

The API defaults to loopback and serves a compact administration dashboard at `/admin`. The first registered user becomes administrator and closes public registration. SQLite stores accounts, roles, session hashes, token hashes and audit history. Browser sessions use HttpOnly cookies with CSRF protection; integrations use scoped, expiring, individually revocable bearer tokens issued through the dashboard. HTTP and WebSocket authorization follows the user's current role, including after AI planning. Delayed AI results expire and cannot override a newer command or stop. Configuration rejects unknown fields and unsafe values before hardware initialization. See [software.md](software.md#api-access) for setup, remote access and the hardware validation sequence.

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
