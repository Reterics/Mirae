# Software stack

How the robot software is built, and how it runs on Windows, macOS, CI and the Pi 5 from one codebase. For the system-level view see [architecture.md](architecture.md); for pins see [wiring.md](wiring.md).

## Decisions

| Area | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.11 | Pi OS Bookworm ships 3.11, Trixie 3.13. CI tests both. |
| Packaging | One `mirae` package, `src/` layout, [uv](https://docs.astral.sh/uv/) + `uv.lock` | Same locked deps on every OS. Plain `pip install -e .` also works. |
| Process model | One asyncio process | Simple to run and debug. Blocking I/O and inference go to worker threads. Subsystems talk over an in-process event bus, so one can move to its own process later. |
| Hardware access | Hardware abstraction layer with `sim` and `pi` backends | Everything above the HAL runs unchanged on a laptop. Pi libraries are imported only when the `pi` backend is built. |
| GPIO | gpiozero on lgpio | The Pi 5's RP1 chip breaks `RPi.GPIO`. |
| ToF | `vl53l1x` over I2C (`smbus2`) | |
| Camera | `picamera2` on the Pi, OpenCV webcam for development | picamera2/libcamera are apt-only, hence the `--system-site-packages` venv on the Pi. |
| Detection | onnxruntime + a permissively licensed model (TBD, e.g. YOLOX-Nano, Apache-2.0) | Avoids AGPL detector stacks. A Hailo AI HAT can slot in behind `Detector` later. |
| STT | faster-whisper (int8, CPU) | Runs on Pi 5 ARM64 and dev machines. A LAN/remote backend can sit beside it. |
| TTS | Piper | Fast, local, good ARM support. |
| LLM | Any OpenAI-compatible endpoint (Ollama by default), plus an offline fake | One client covers Ollama, llama.cpp, LM Studio, vLLM and hosted APIs. |
| API | FastAPI + uvicorn: REST plus a telemetry WebSocket | |
| Config | TOML profiles (`sim`, `pi`) + an optional user file, validated by pydantic | |
| Quality | ruff (lint + format), mypy `--strict`, pytest | |

## Runtime

```text
                      ┌─────────────── EventBus (pub/sub) ───────────────┐
                      │ telemetry · behavior.intent/state · speech.* ·   │
                      │ vision.detections                                │
                      └──────────────────────────────────────────────────┘
 FastAPI ─┬─ /api/movement, /api/drive ──────────────────────┐
          ├─ /api/intent ───────────────┐                    │
          └─ /api/ai/command ─► IntentPlanner ─► Intent ─► BehaviorEngine ─► SafetyGovernor
                               (LLMProvider)    (validated)   (state machine)        │
                                                                                     ▼
 range loop (20 Hz, thread) ─► VL53L1X ─► governor.update_range       control loop (50 Hz)
                                                                    governor ─► motors
                                                                    encoders ─► odometry
                                                                    publish telemetry
```

* **Control loop** (`robot.py`, 50 Hz): reads the governor's output, writes the motors, reads encoders, updates odometry and publishes telemetry. If the loop exits for any reason, the motors stop.
* **Range loop**: reads the ToF sensor in a worker thread. A failed read counts as "no reading".
* **Vision and speech** (V0.3/V0.4): each will be a task that reads its device in a thread, runs inference and publishes to the bus. The behavior engine consumes `vision.detections` to drive FOLLOW and APPROACH.

## Safety contract

`SafetyGovernor` is the only path to the motors. Its rules are deterministic, involve no AI or network, and are unit tested with a fake clock:

| Rule | Effect |
|---|---|
| E-stop latched | Zero output, and commands are ignored. `/api/estop/release` never resumes motion; a new command is needed. |
| Command expired (deadman) | Zero output. A command without `duration_s` lasts 0.5 s; `duration_s` is capped at 5 s. |
| Speed limit | Clamped to `safety.max_speed` (0.6) |
| Obstacle ≤ 120 mm, or no range reading for 0.5 s | Forward component removed. Turning in place and reversing are still allowed. |
| Obstacle 120–300 mm | Forward component scaled down linearly |

The LLM can only produce one of the [intents](../src/mirae/behavior/intents.py) (`stop`, `move`, `turn`, `approach_person`, `follow_person`, `explore`, `say`, `sleep`), and each one has bounded speed and duration. Invalid output is dropped; it never causes motion.

**API consequence:** movement commands expire. A joystick client re-sends `/api/drive` while the stick is held, at 5–10 Hz. A one-shot client passes `duration_s`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness |
| GET | `/api/status` | Telemetry snapshot: behavior, safety, wheels, encoders, pose |
| POST | `/api/movement` | `{"action": "forward", "speed": 0.3, "duration_s": 1}` |
| POST | `/api/drive` | `{"linear": 0.3, "angular": -0.2}`, values in [-1, 1] |
| POST | `/api/stop`, `/api/estop`, `/api/estop/release` | |
| POST | `/api/intent` | Send an intent directly, e.g. `{"action": "turn", "direction": "left"}` |
| POST | `/api/ai/command` | `{"text": "turn left"}` → LLM → intent |
| POST | `/api/sim/range` | Sim only: set the simulated obstacle distance |
| WS | `/ws/telemetry` | Telemetry stream at `api.telemetry_hz` |

Interactive docs are at `http://<host>:8000/docs`.

## Repository layout

```text
src/mirae/
├── core/        clock (injectable), event bus
├── hardware/    base.py interfaces · sim.py · pi.py (TB6612FNG, encoders, VL53L1X)
├── safety/      SafetyGovernor
├── drive/       kinematics, odometry, DriveController
├── behavior/    intents (the AI vocabulary), BehaviorEngine state machine
├── ai/          LLMProvider (fake, OpenAI-compatible), IntentPlanner
├── vision/      CameraSource, Detector (picamera2 / OpenCV sources)
├── speech/      SpeechToText, TextToSpeech (faster-whisper, Piper stub)
├── api/         FastAPI app
├── profiles/    sim.toml, pi.toml
├── config.py    typed config + loader
├── robot.py     runtime wiring and loops
└── cli.py       `mirae run`, `mirae config`
tests/           pytest suite, sim backend only
deploy/          Pi install script, systemd unit, config.txt snippet
.github/         CI
```

## Development (Windows, macOS, Linux)

```bash
uv sync                          # creates .venv with dev tools
uv run mirae run                 # sim robot on http://127.0.0.1:8000/docs
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Optional extras: `uv sync --extra vision --extra speech` (webcam, ONNX, Whisper, Piper). To use a local Ollama, create `mirae.local.toml`:

```toml
[ai]
provider = "openai_compat"
base_url = "http://localhost:11434/v1"
model = "llama3.2"
```

Then run `uv run mirae --config mirae.local.toml run`.

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

* **lint:** ruff, ruff format, mypy
* **test:** Ubuntu, Windows and macOS × Python 3.11 and 3.13, sim backend
* **pi-deps-arm64:** installs the `pi`, `vision` and `speech` extras on an ARM64 runner and runs the tests. It catches missing aarch64 wheels before they reach the robot. It needs `ubuntu-24.04-arm` runners, which are free for public repos.

## Deploying to the Pi

1. Flash Raspberry Pi OS (64-bit) and enable SSH.
2. Append [`deploy/pi/config.txt.snippet`](../deploy/pi/config.txt.snippet) to `/boot/firmware/config.txt`, then reboot.
3. `git clone` the repo, then run `sudo bash deploy/pi/install.sh pi` (or `pi,vision,speech`).
4. Edit `/etc/mirae/mirae.toml` for this robot (pins, inversion, AI endpoint), then `sudo systemctl restart mirae`.
5. Follow the logs with `journalctl -u mirae -f`.

## Known risks and open questions

* **Encoder rate.** Quadrature decoding runs in Python callbacks. At full speed the N20 encoders give a few kHz of edges per wheel, which is near the limit. Measure first. Fallbacks: decode a single channel, or count on a small microcontroller. The `WheelEncoders` interface stays the same either way.
* **Encoder counts per revolution** are assumed (150:1 × 7 PPR = 1050). Measure and set `drive.encoder_counts_per_rev`.
* **PWM:** lgpio software PWM is the default. Hardware PWM on GPIO12/13 is the upgrade path if motor drive is jittery.
* **I2S overlay:** the mic and amp share I2S. The `googlevoicehat-soundcard` overlay is the usual choice for this pair but hasn't been verified on this robot yet.
* **numpy vs picamera2 on the Pi:** the venv sees apt packages, but the `vision` and `speech` extras pip-install numpy. That copy can shadow the apt numpy that picamera2 and simplejpeg were built against, which causes ABI errors. Verify on hardware. A possible fix is to skip pip's numpy on the Pi when the system one is present.
* **Untested on hardware:** everything in `hardware/pi.py`, `vision/sources.py` and `speech/engines.py`. CI only checks that it installs and imports.
* **Not started:** closed-loop wheel PID, the detection model choice, the audio I/O pipeline, wake word, and a web UI.
