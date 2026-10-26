# Software stack

How the robot software is built, and how it runs on Windows, macOS, CI and the Pi 5 from one codebase. For the system-level view see [architecture.md](architecture.md); for pins see [wiring.md](wiring.md).

## Decisions

| Area | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.11 | Pi OS Bookworm ships 3.11, Trixie 3.13. CI tests both. |
| Packaging | One `mirae` package, `src/` layout, [uv](https://docs.astral.sh/uv/) + `uv.lock` | Same locked deps on every OS. Plain `pip install -e .` also works. |
| Process model | One asyncio process, dedicated range-sensor and motor-watchdog threads | Sensor reads and cutoff do not depend on API scheduling. Inference must run outside the control loop; subsystems communicate over a bounded event bus. |
| Hardware access | Hardware abstraction layer with `none` and `pi` backends | Administration and local processing run without a robot backend. Pi libraries are imported only when physical drivers are built. |
| GPIO | gpiozero on lgpio | The Pi 5's RP1 chip breaks `RPi.GPIO`. |
| ToF | `vl53l1x` over I2C (`smbus2`) | |
| Camera | `picamera2` on the Pi, OpenCV webcam for development | picamera2/libcamera are apt-only, hence the `--system-site-packages` venv on the Pi. |
| Detection | OpenCV DNN (SSD-compatible model supplied locally), optional face_recognition | No bundled weights or automatic downloads. Face matches use measured embedding distance. |
| STT | faster-whisper (int8, CPU) | Runs on Pi 5 ARM64 and dev machines. A LAN/remote backend can sit beside it. |
| TTS | Piper | Fast, local, good ARM support. |
| LLM | Explicitly selected OpenAI-compatible endpoint; disabled by default | One client covers Ollama, llama.cpp, LM Studio, vLLM and hosted APIs. |
| API | FastAPI + uvicorn: REST plus a telemetry WebSocket | |
| Config | TOML profiles (`local`, `pi`) + user file + managed SQLite settings, validated by pydantic | |
| Quality | ruff (lint + format), mypy `--strict`, pytest | |

## Desktop installation and verification

Use Python 3.13 for the desktop camera and speech stack (the base server also
tests Python 3.11). `uv` can download the interpreter; macOS's system Python 3.9
is too old.

```bash
uv sync --locked --python 3.13 --extra vision --extra speech
uv run --no-sync mirae run
```

Use `--no-sync` to run the environment prepared by the dashboard. A subsequent
plain `uv sync` or `uv run --exact` can remove optional packages installed there.
When syncing again, include the extras you want to keep.

| Platform | Native prerequisites and device access |
|---|---|
| macOS (Apple Silicon or Intel) | Camera and microphone access must be enabled for the terminal/IDE/app launching Mirae under System Settings → Privacy & Security. Restart Mirae after granting access. Face recognition additionally needs Xcode Command Line Tools (`xcode-select --install`) and CMake (`brew install cmake` or `uv pip install cmake`). |
| Windows | Allow desktop apps to access the camera and microphone in Windows privacy settings. Face recognition needs Visual Studio's **Desktop development with C++**, Windows SDK and CMake tools. |
| Linux desktop | Install PortAudio (`sudo apt-get install libportaudio2` on Debian/Ubuntu), grant access to the camera/audio devices, and run in a session with working audio. Face recognition additionally needs `build-essential` and `cmake`. |
| Raspberry Pi | Use [deploy/pi/install.sh](../deploy/pi/install.sh) for the system GPIO, I2C and libcamera dependencies. Desktop tests do not validate physical robot hardware. |

In the admin console, check imports, refresh devices, and test the selected
camera/microphone. Camera discovery uses AVFoundation on macOS and DirectShow on
Windows. Microphones and speakers are saved by their device identity. A machine
without a default microphone can still list its speakers and other microphones.

Download and activate an SSD or Whisper model from Local processing. Downloads
are pinned and verified before activation. Piper can be installed from the same
dependency table; supply a voice `.onnx` and its matching `.onnx.json` in
`speech.tts_voice`. Model loading during normal operation never downloads files.

For [Ollama Cloud](https://docs.ollama.com/api/openai-compatibility), add an Ollama
connection with base URL `https://ollama.com/v1` and an API key, check the models,
then select a returned model ID. Local Ollama uses `http://localhost:11434/v1`.
Cloud requests still respect the command expiration deadline; increasing the
connection timeout does not increase the safety deadline.

`uv run --no-sync pytest` runs the offline suite. To additionally download about
165 MB of pinned test models and exercise SSD inference, Piper synthesis and
Whisper transcription/resampling:

```bash
# macOS / Linux
MIRAE_TEST_MODELS=1 uv run --no-sync pytest tests/test_local_engines.py
```

```powershell
# Windows PowerShell
$env:MIRAE_TEST_MODELS = "1"
uv run --no-sync pytest tests/test_local_engines.py
```

CI installs the `faces` extra too and checks native face detection. It runs these
native engine checks on Windows, macOS and Linux with Python 3.13,
in addition to the base server matrix and the ARM64 dependency job. Camera,
microphone and physical Pi hardware access require tests on the target machine.

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

* **Control loop** (`robot.py`, 50 Hz): reads the governor's output, writes the motors through the watchdog, reads encoders and updates odometry. It skips missed ticks rather than replaying them in a burst, and publishes telemetry at `api.telemetry_hz`. If it exits, motor output is cut.
* **Motor watchdog**: a separate thread cuts output at the command deadline, even while asyncio is blocked. Missing control heartbeats for `safety.motor_watchdog_s` (0.2 s) latch a runtime fault; API e-stop release cannot clear it. Restart the runtime after investigating the fault.
* **Range worker**: a dedicated thread owns both ToF reads and close. A failed read counts as "no reading". A read exceeding `hardware.tof.read_timeout_s` (0.5 s) faults the runtime; a stuck sensor is only closed when its read returns. Samples keep their acquisition timestamps when passed to the governor.
* **Supervision**: an unexpected loop exit stops motion and cancels the other loop. The CLI shuts down the server and exits unsuccessfully so systemd can restart it. Health includes control progress, sensor progress and watchdog state. Telemetry includes the fault, maximum tick lateness and missed ticks.
* **Administration without hardware**: the default `local` profile runs service telemetry and configured local processing only. Motor, encoder, range, odometry and safety readings are null; movement receives HTTP 503. Physical initialization failure leaves administration available with the actual error, never a synthetic replacement.
* **Vision and speech**: optional daemon workers read actual camera/audio input and publish detections/transcripts to the bus. OpenCV DNN, face_recognition and faster-whisper need installed dependencies and local model files. Missing dependencies/devices produce an error with no sample. Automatic model downloads are disabled. Voice commands and face-following autonomy are not wired into these workers.

## Safety contract

`SafetyGovernor` is the only path to the motors. Its rules are deterministic, involve no AI or network, and are unit tested with a fake clock:

| Rule | Effect |
|---|---|
| E-stop latched | Zero output, and commands are ignored. `/api/estop/release` never resumes motion; a new command is needed. |
| Command expired (deadman) | Zero output. A command without `duration_s` lasts 0.5 s; `duration_s` is capped at 5 s. |
| Speed limit | Clamped to `safety.max_speed` (0.6) |
| Obstacle ≤ 120 mm, or no range reading for 0.5 s | Forward component removed. Turning in place and reversing are still allowed. |
| Obstacle 120–300 mm | Forward component scaled down linearly |
| Speeding up | Each wheel's output rises at most `safety.ramp_per_s` (1.5 duty per second, so 0.4 s from stop to 0.6). Slowing down, stopping, e-stop and the deadman act at once; a reversal starts again from zero. Only the wheels push, so a sudden full-duty start can lift the caster, worst when pulling away uphill. This limits the duty, not the acceleration itself: the motors' stall torque isn't published. |

The LLM can only produce one of the [intents](../src/mirae/behavior/intents.py) (`stop`, `move`, `turn`, `approach_person`, `follow_person`, `explore`, `say`, `sleep`), and each one has bounded speed and duration. Invalid output is dropped; it never causes motion.

Hard forward limits are enforced again after ramping, without increasing reverse wheel output. Invalid sensor values (negative, NaN or infinity) count as missing readings. Configuration is immutable and rejects unknown keys, nonfinite numbers, invalid dimensions/frequencies, overlapping GPIO pins and inconsistent thresholds.

Only one AI request may plan at a time; overlapping requests receive HTTP 429. A stop, e-stop/release or newer command invalidates pending AI results (HTTP 409). Planning also expires after `ai.command_ttl_s` (5 s), or `ai.timeout_s` if shorter (HTTP 504). An invalid or expired result never starts a new movement.

The software watchdog requires the Python interpreter and GPIO driver to remain responsive. It cannot protect against power loss, a native call holding the GIL, or a stuck driver. Fit and validate an independent physical heartbeat cutoff/e-stop before unattended operation. Output cutoff also does not guarantee instant mechanical braking; measure stopping distance on the actual floor.

**API consequence:** movement commands expire. A joystick client re-sends `/api/drive` while the stick is held, at 5–10 Hz. A one-shot client passes `duration_s`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Runtime health; HTTP 503 after a loop or worker stalls/fails |
| GET | `/api/status` | Telemetry snapshot: behavior, safety, wheels, encoders, pose |
| POST | `/api/movement` | `{"action": "forward", "speed": 0.3, "duration_s": 1}` |
| POST | `/api/drive` | `{"linear": 0.3, "angular": -0.2}`, values in [-1, 1] |
| POST | `/api/stop`, `/api/estop`, `/api/estop/release` | |
| POST | `/api/intent` | Send an intent directly, e.g. `{"action": "turn", "direction": "left"}` |
| POST | `/api/ai/command` | `{"text": "turn left"}` → LLM → intent |
| GET | `/api/actions` | Optional actions (currently `story`) and whether each is on |
| PUT | `/api/actions/{id}` | Turn an action on or off: `{"enabled": false}` |
| GET | `/api/story` | Story state, the last three episodes, and whether one is being written |
| PUT | `/api/story` | Start a new story (replaces the old one): `{"premise", "protagonist", "cast": [{"name", "role", "description"}]}` |
| POST | `/api/story/tell` | Write and say tonight's episode; `{"sleep": true}` puts Mirae to sleep afterwards |
| WS | `/ws/telemetry` | Telemetry stream at `api.telemetry_hz` |

### Story

Story is an optional action: turn it on or off on the dashboard's **Actions** page (on by default). While it is off, `PUT /api/story` and `POST /api/story/tell` return HTTP 409; the story and its episodes are kept.

Mirae tells one serial story, one episode per night, and keeps it consistent between nights. Each episode prompt has three parts: the long-term reference (fixed genre and premise plus a rolling summary of at most 1500 characters; the model is told to stay in the genre), the current state (main character, active cast, departed characters) and the current situation (where the last episode ended).

An episode takes two LLM calls. The first writes plain prose. The second returns JSON continuity notes: who joined, who left or died, the new summary and the closing situation. Code applies the notes, not the model: a removal must name an active cast member, the main character never leaves, characters who died never return, characters who left may come back, and the cast holds at most 12. If the notes are invalid, the episode is still saved, the cast and summary stay as they were, and the situation becomes the episode's last paragraph. Episodes and state are saved in one SQLite transaction in `api.database_path`; an episode written against a story that changed meanwhile is rejected with HTTP 409.

Generation is bounded by `ai.story_timeout_s` (300 s) and aims for `ai.story_words` (350). The story is text and never produces motion. The episode is published on `speech.say` and spoken by the speaker service.

### Voice

The speaker service (`speech/speaker.py`) speaks everything published on `speech.say`: story episodes and `say` intents. Configure it on the dashboard's **Actions** page under **Voice**:

| `speech.tts` | Engine | Notes |
|---|---|---|
| `elevenlabs` | ElevenLabs over HTTPS (`elevenlabs_voice_id`, `elevenlabs_model`, default `eleven_v4`) | Sends the text to ElevenLabs. The API key is stored encrypted with the LLM credentials and never returned by the API. |
| `piper` | Piper, local and offline (`tts_voice` = path to a `.onnx` voice with its `.onnx.json`) | Needs the `speech` extra. |
| `none` | Off | Default. |

Speaking does not depend on `speech.enabled`, which only controls listening. Playback goes to `speech.output_device` (a `"<host API>:<name>"` identity, null for the system default). `GET /api/speech` reports the state, `GET /api/speech/last.wav` returns the last clip, `POST /api/speech/say` speaks a text and `POST /api/speech/stop` stops playback and drops queued speech.

The administration console is at `http://<host>:8000/admin`. The OpenAPI schema is at `/openapi.json`; the dashboard uses local assets and makes no third-party requests.

### API access

Both profiles bind to `127.0.0.1` by default. Prefer an SSH tunnel for remote control:

```bash
ssh -L 8000:127.0.0.1:8000 user@robot
```

On a fresh installation, open `/admin` and create the first user. This user is always an administrator. Registration closes as soon as any user exists; concurrent registration attempts cannot create a second bootstrap administrator. Complete setup over loopback or an SSH tunnel before exposing a new installation to a network. Environment-based API keys (`api.token_env`) have been removed.

The light, compact administration dashboard uses the Mirae logo and bundled IBM Plex Sans. Runtime shows measured service information and active processing. LLM connections, local processing and hardware settings have dedicated views alongside users, roles, API keys and audit history. There are no seeded demo records or synthetic physical readings. Administrators create users, change roles, disable/delete accounts and reset passwords. The last active administrator cannot be deleted, disabled or demoted. Administrator, Operator and Viewer are protected built-in roles; custom roles have editable permission sets. Operator can read/control the robot; releasing e-stop requires a separate permission granted to Administrator by default. Frontend visibility follows permissions; the server enforces them independently.

Browser sign-in uses an opaque HttpOnly, SameSite=Strict cookie, stored only as a hash server-side. Mutating cookie-authenticated requests require the `X-CSRF-Token` returned by `/api/auth/login` or `/api/auth/me`; cross-origin access is rejected. Sessions expire after `api.session_hours` (12 hours by default). The Account control changes your own password. Passwords use salted scrypt (N=32768, r=8, p=3); login hashing is bounded and login attempts are rate-limited. Password changes/resets revoke all sessions and API keys for that user. Disabling a user also revokes credentials so re-enabling never restores old API keys.

Create a named key in **API keys**, choose an active owner, scopes and expiry (1–365 days), then copy the secret displayed once. Only its hash and display prefix are persisted. Integrations send `Authorization: Bearer <key>`; keys are never accepted in query strings. Effective permissions are the intersection of the key's scopes and its owner's current role. Scopes cannot exceed the issuer's permissions at creation. Revocations, expiry and role changes are checked on each HTTP request and each telemetry WebSocket message. AI commands recheck authorization after planning. Browser WebSockets use the session cookie directly, with an Origin check.

All robot APIs require authentication even on loopback; before setup, robot control remains locked. Only setup status, first-user registration, login and dashboard assets are public. Authentication failures return HTTP 401 or WebSocket close code 1008, insufficient permission returns HTTP 403, and blocked bootstrap/last-admin/role operations return 403 or 409. Access changes and successful/denied sign-ins appear in the audit log; credential secrets never do. Request bodies are limited to 16 KiB, and dashboard responses disable caching and use a restrictive Content Security Policy.

Accounts, sessions, API keys and audit history persist in `api.database_path`: `var/mirae.sqlite3` under the local profile, `/var/lib/mirae/mirae.sqlite3` under the Pi profile. The database uses versioned SQLite tables and WAL; each worker operation owns its connection. Back up the database using SQLite's backup API (or stop Mirae and copy the database plus any WAL files); protect backups as credentials. Systemd creates the Pi state directory with mode 0700. Redeploying preserves this directory and excludes local runtime databases from source synchronization. Network access should use TLS termination or an SSH tunnel; when serving HTTPS, set `api.cookie_secure = true`.

| Method | Path | Access management |
|---|---|---|
| GET | `/api/auth/status` | Whether first-run registration is open |
| POST | `/api/auth/register`, `/api/auth/login` | First administrator / browser sign-in |
| GET / POST | `/api/auth/me`, `/api/auth/logout`, `/api/auth/password` | Current session, logout, own password change |
| GET / POST / PATCH / DELETE | `/api/admin/users[/{id}]` | User lifecycle; `users:manage` |
| GET / POST / PUT / DELETE | `/api/admin/roles[/{id}]` | Custom roles; `roles:manage` |
| GET / POST / DELETE | `/api/admin/tokens[/{id}]` | Credential issue/list/revoke; `tokens:manage` |
| GET | `/api/admin/audit` | Latest 100 events; `audit:read` |

Role/user pickers are readable by users, roles and API key managers. Mutations require the specific management permission. Role management can grant powerful permissions and should be limited to trusted administrators.

## Repository layout

```text
src/mirae/
├── core/        clock (injectable), event bus
├── hardware/    base.py interfaces · sim.py · pi.py (TB6612FNG, encoders, VL53L1X)
├── safety/      SafetyGovernor
├── drive/       kinematics, odometry, DriveController
├── behavior/    intents (the AI vocabulary), BehaviorEngine state machine
├── ai/          LLMProvider (OpenAI-compatible), IntentPlanner
├── vision/      CameraSource, Detector (picamera2 / OpenCV sources)
├── speech/      SpeechToText, TextToSpeech (faster-whisper, Piper stub)
├── api/         FastAPI app
├── profiles/    local.toml, pi.toml
├── config.py    typed config + loader
├── robot.py     runtime wiring and loops
└── cli.py       `mirae run`, `mirae config`
tests/           pytest suite, isolated accounts and explicitly injected hardware mocks
deploy/          Pi install script, systemd unit, config.txt snippet
.github/         CI
```

## Development (Windows, macOS, Linux)

```bash
uv sync                          # creates .venv with dev tools
uv run mirae run                 # administration at http://127.0.0.1:8000/admin
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Optional extras: `uv sync --extra vision --extra faces --extra speech`. Packages can also be installed explicitly from **Local processing → Install**. The service must run in a writable virtual environment. Picamera2/libcamera and Linux PortAudio remain operating-system packages; install them with the Pi deployment prerequisites.

### Managed pipeline

Administrators with `pipeline:manage` configure Ollama, LM Studio, OpenAI or another OpenAI-compatible endpoint under **LLM connections**. **Check / models** makes a bounded request to the actual endpoint and records its status, latency and returned model IDs. Select a model returned by that endpoint before activating it. Selection stops motion and invalidates pending commands. Disabling clears the active provider. Endpoint changes discard any retained credential unless it is explicitly supplied again.

Provider keys are write-only and Fernet-encrypted in SQLite. The encryption key is stored alongside the database with a `.key` suffix and restricted file permissions. Back up both database and key, protect them together, and never commit either to source control. The admin never returns a stored provider key; robot API keys remain separate hashed credentials.

**Local processing** provides allowlisted **Install** buttons for camera discovery/OpenCV, face_recognition, audio capture and faster-whisper. Installation uses the service's own Python environment. Install/download operations run in background threads with persistent SQLite status and bounded console logs; the progress dialog polls actual output, supports cancellation, and can be reopened under **Operations**. Arbitrary package names, shell commands and model URLs are not accepted. Stop local processing before changing its packages. Compiled packages such as dlib require the platform's build tools; installer failures remain visible in the console.

The model catalog offers MobileNet SSD (20 Pascal VOC object classes) and multilingual Whisper tiny/base/small. **Download** fetches files from pinned upstream revisions and verifies size/content hashes before marking a model available. **Activate** supplies the model's preprocessing and local file paths and starts processing. OpenCV is pinned to 4.13.0.92 because OpenCV 5 removed the Caffe importer used by this SSD model. No models are fetched automatically at service startup or inference time.

**Configure vision/camera** discovers named cameras and places automatic physical-camera selection first. Windows uses DirectShow device enumeration, including USB and virtual-camera names. Camera identity is retained across index changes. **Capture test frame** returns a real JPEG and reuses the running vision worker; a failed/stopped worker does not prevent testing its camera again. Default capture is 640×480 at 5 FPS. Optional face recognition uses locally supplied NPZ encodings.

**Configure speech recognition** lists all detected input devices, including their host APIs, with **System default** first. Whisper base, CPU int8, automatic language detection and four-second audio chunks are the defaults. Microphones that reject 16 kHz use their native sample rate and are resampled for Whisper. A bounded audio queue keeps capture running during inference. **Test microphone** records two seconds and reports real device/sample-rate/level information, or inspects the active speech worker. **Save & start** waits for actual worker readiness and reports startup errors instead of claiming success after merely saving settings. **Stop** releases the device.

**Hardware** shows initialized physical drivers and their samples, or an empty device table. Configure GPIO, range sensor, wheel geometry and safety limits here. Saved hardware/drive/safety changes are validated and marked pending until a runtime restart. Configured calibration defaults are settings, never presented as measured readings.


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

The installer stops an existing service before replacing runtime files. Invalid configuration fails before GPIO initialization. Partial hardware initialization releases devices already opened and keeps the motor driver's STBY pin low until an authenticated command is written. Normal stop and watchdog cutoff lower STBY before stopping both wheel outputs.

Before floor testing, raise the wheels and verify polarity/encoders, e-stop/release, client disconnect/command expiry, sensor disconnect and stalled-loop cutoff. Under camera/speech and API load, inspect `runtime.max_tick_lateness_s` and `runtime.missed_ticks`; the control period is 20 ms. Measure encoder counts, stopping distance and GPIO/PWM behavior on the Pi before tuning speed or enabling autonomy.

## Known risks and open questions

* **Encoder rate.** Quadrature decoding runs in Python callbacks. At full speed the N20 encoders give a few kHz of edges per wheel, which is near the limit. Measure first. Fallbacks: decode a single channel, or count on a small microcontroller. The `WheelEncoders` interface stays the same either way.
* **Encoder counts per revolution** are assumed (150:1 × 7 PPR = 1050). Measure and set `drive.encoder_counts_per_rev`.
* **PWM:** lgpio software PWM is the default. Hardware PWM on GPIO12/13 is the upgrade path if motor drive is jittery.
* **I2S overlay:** the mic and amp share I2S. The `googlevoicehat-soundcard` overlay is the usual choice for this pair but hasn't been verified on this robot yet.
* **numpy vs picamera2 on the Pi:** the venv sees apt packages, but the `vision` and `speech` extras pip-install numpy. That copy can shadow the apt numpy that picamera2 and simplejpeg were built against, which causes ABI errors. Verify on hardware. A possible fix is to skip pip's numpy on the Pi when the system one is present.
* **Untested on hardware:** everything in `hardware/pi.py`, `vision/sources.py` and `speech/engines.py`. CI only checks that it installs and imports.
* **Not complete:** closed-loop wheel PID, selection/licensing of production detector weights, wake word, speech-to-intent wiring, face-following autonomy and TTS playback. Optional inference and physical drivers still need validation on the target hardware.
