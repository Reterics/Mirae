# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Mirae is a small Raspberry Pi 5 companion robot. The repo holds three loosely coupled things: the robot software (`src/mirae/`, Python), the website (`site/`, React + Vite, deployed to GitHub Pages), and the hardware docs and printable exports (`docs/`, `cad/`). The project is an early prototype: no physical robot has been built yet, and the Pi hardware drivers are untested on real hardware.

## Commands

### Robot software (repo root, uv)

```bash
uv sync                                   # dev env (.venv) with pytest, ruff, mypy
uv run mirae run                          # sim robot; API docs at http://127.0.0.1:8000/docs
uv run mirae --config mirae.local.toml run   # with a local config override (git-ignored)
uv run pytest                             # all tests (sim backend only)
uv run pytest tests/test_safety.py::test_deadman_expires_command   # single test
uv run ruff check . && uv run ruff format --check . && uv run mypy  # what CI's lint job runs
```

mypy runs in `--strict` mode over `src` and `tests`. Ruff line length is 100. CI tests Python 3.11 (Pi OS Bookworm) and 3.13 (Trixie) on Linux, Windows and macOS, so code must stay 3.11-compatible. A separate ARM64 job installs the `pi`, `vision` and `speech` extras.

### Website (`site/`)

```bash
npm ci
npm run dev            # Vite dev server
npm run check          # typecheck + eslint + prettier --check (CI runs these plus build)
npm run build          # tsc --noEmit && vite build -> site/dist
npm run format         # prettier --write
```

Use `npm run typecheck`, not `npx tsc`: in this shell `npx tsc` is rewritten to a different binary and reports false errors.

## Robot software architecture

One asyncio process (`robot.py`) wires everything together. A 50 Hz control loop steps the drive controller, ticks the behavior engine and publishes telemetry; if the loop ever exits, the motors stop. A range loop reads the ToF sensor in a worker thread. Subsystems talk over an in-process `EventBus` (`core/bus.py`, topics in `Topics`).

Control flows one way, and only `SafetyGovernor` (`safety/governor.py`) may produce motor output:

```text
API / LLM -> IntentPlanner -> Intent -> BehaviorEngine -> SafetyGovernor -> DriveController -> motors
```

- **The LLM never drives motors.** `ai/planner.py` turns text into one of the bounded intents in `behavior/intents.py`; invalid output is dropped. Keep new AI features inside this intent vocabulary.
- **Safety rules are deterministic** (no AI, no network): e-stop latch (release never resumes motion), deadman expiry (0.5 s default, `duration_s` capped at 5 s), speed clamp, and forward motion blocked or scaled by ToF distance or a stale reading. The full contract is in `docs/software.md`. Because commands expire, API clients must re-send `/api/drive` while moving.
- **Hardware abstraction:** `hardware/base.py` defines the interfaces; `hardware/sim.py` is the simulated backend and `hardware/pi.py` the real one (gpiozero/lgpio, VL53L1X). Pi libraries are imported only when the `pi` backend is built, so everything else runs on any OS. `lgpio` and `picamera2` are apt-only on the Pi (the venv uses `--system-site-packages`, see `deploy/pi/install.sh`).
- **Time is injectable:** pass a `Clock`; tests use `core.clock.FakeClock` to step time deterministically.
- **Config** (`config.py`): pydantic models, then the built-in profile `profiles/<sim|pi>.toml`, then an optional user file (`--config` or `MIRAE_CONFIG`, e.g. `/etc/mirae/mirae.toml`). Later wins, deep-merged. Pin defaults in `config.py` must match the table in `docs/wiring.md`.
- **AI providers** (`ai/providers.py`): `none`, `fake` (offline), or any OpenAI-compatible endpoint (Ollama by default).

## Website architecture

- React 19 + TypeScript, Tailwind v4 via `@tailwindcss/vite` with **no preflight** (own base layer in `src/styles/index.css`). Breakpoints are custom variants `max-1080:`, `max-960:`, `max-560:`. Shared class lists live in `src/ui.ts`.
- One `index.html` with `HashRouter` (`#/assembly`). `vite.config.ts` uses `base: "./"` because the site is also deployed to an unknown sub-folder, so every asset path must be relative.
- Head tags are injected from `src/site.ts`; page copy and data live in `src/content.tsx` (edit text there, not in section components).
- The production build injects a strict CSP: everything same-origin, no CDNs, no inline scripts/styles, no `data:` URIs (`assetsInlineLimit: 0`), no wasm (so no Draco/meshopt in GLBs). Bundle every dependency and font locally.
- Brand images are imported from the repo's `../assets/brand/` and served in dev by a custom middleware in `vite.config.ts`.
- The assembly guide (`src/assembly/`): `steps.tsx` must follow the same order as the assembly list in `cad/README.md`. The three.js viewer loads the prebuilt `public/media/assembly/assembly.glb` with `viewer/model.json`. The wiring diagrams parse `docs/wiring.md` at build time (`wiring/pins.ts` via `?raw`), so that table is the single source for both the doc and the diagrams; don't hard-code connections in the site.
- Media in `site/public/media/` and generated `src/**/*.json` are committed outputs. They are produced by private tooling (`site/build_media.py`, `cad/blender/*`), which is git-ignored, and CI builds without it.

## Hardware and CAD

- `docs/parts.md` holds the verified part dimensions; `docs/hardware.md` the shopping list (HESTORE part numbers); `docs/wiring.md` the pin map. Never invent part sizes or parts: they come from the vendor (HESTORE pages/drawings) or the maintainer's measurements, and unknown values are marked as such (`MEASURE`).
- CAD sources, Blender scripts and render tooling (`cad/blender/`, `cad/low-poly/`, `cad/reference/`) are private and git-ignored; only the STL exports and renders are tracked. When they are present locally, enclosure changes go through `cad/blender/build_mirae.py` and its gated checks.
- The AI HAT+ 2 is optional everywhere (docs, guide, CAD).
- Git LFS stores `*.stl`, `*.glb`, `*.mp4`, `*.webm`, `*.blend` and model weights. Run `git lfs install --local` after cloning.
