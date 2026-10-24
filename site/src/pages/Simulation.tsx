import { useCallback, useEffect, useRef, useState } from "react";

import { SkipLink } from "../components/SkipLink";
import { Header } from "../sections/Header";
import { cx } from "../lib";
import { ComponentHud } from "../simulation/ComponentHud";
import { DRIVE_KEYS, driveCommand, type DriveAction } from "../simulation/drive";
import { DEFAULT_SETTINGS, type PhysicsSettings } from "../simulation/physics";
import { SimulationStage, type Telemetry } from "../simulation/stage";
import "../simulation/simulation.css";

const CONTROLS: readonly { action: DriveAction; label: string; key: string; arrow: string }[] = [
  { action: "forward", label: "Forward", key: "W", arrow: "↑" },
  { action: "left", label: "Turn left", key: "A", arrow: "←" },
  { action: "reverse", label: "Reverse", key: "S", arrow: "↓" },
  { action: "right", label: "Turn right", key: "D", arrow: "→" },
];
const PARAMETERS: readonly {
  key: keyof PhysicsSettings;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "slope", label: "Uphill / downhill", min: -30, max: 30, step: 1, unit: "°" },
  { key: "crossSlope", label: "Cross slope", min: -30, max: 30, step: 1, unit: "°" },
  { key: "comHeight", label: "CoM above ground", min: 35, max: 120, step: 1, unit: " mm" },
  { key: "comForward", label: "CoM ahead of axle", min: -15, max: 80, step: 1, unit: " mm" },
  { key: "friction", label: "Tire friction", min: 0.1, max: 1.2, step: 0.05, unit: " μ" },
  { key: "torque", label: "Torque limit / motor", min: 5, max: 196, step: 1, unit: " mN·m" },
];

export function Simulation() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const stage = useRef<SimulationStage | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [inputs, setInputs] = useState<ReadonlyMap<string, DriveAction>>(() => new Map());
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [paused, setPaused] = useState(false);
  const [showSupport, setShowSupport] = useState(true);
  const [huds, setHuds] = useState({ components: false, firstPerson: false });
  const [camera, setCamera] = useState(false);
  const [sensor, setSensor] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const actions = new Set(inputs.values());
  const drive = driveCommand(actions);
  const changeInput = useCallback((source: string, action?: DriveAction): void => {
    setInputs((current) => {
      const next = new Map(current);
      if (action) next.set(source, action);
      else next.delete(source);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!canvas.current) return;
    let active = true;
    let instance: SimulationStage | undefined;
    void Promise.resolve()
      .then(async () => {
        if (!active || !canvas.current) return;
        instance = new SimulationStage(canvas.current, DEFAULT_SETTINGS, setTelemetry);
        stage.current = instance;
        await instance.ready;
        if (stage.current === instance) setReady(true);
      })
      .catch(() => {
        if (active) setError("The physics environment could not load. Reload to try again.");
      });
    return () => {
      active = false;
      instance?.dispose();
      stage.current = null;
    };
  }, []);
  useEffect(() => {
    stage.current?.setInput({ left: drive.left, right: drive.right }, camera, sensor);
  }, [drive.left, drive.right, camera, sensor]);
  useEffect(() => {
    stage.current?.setPaused(paused);
  }, [paused]);
  useEffect(() => {
    stage.current?.setSupportVisible(showSupport);
  }, [showSupport]);
  useEffect(() => {
    if (!viewport.current) return;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setHuds({ components: width >= 1000 && height >= 440, firstPerson: width >= 1000 && height >= 680 });
    });
    observer.observe(viewport.current);
    return () => {
      observer.disconnect();
    };
  }, []);
  const resetExperiment = useCallback((): void => {
    setInputs(new Map());
    stage.current?.setInput({ left: 0, right: 0 }, camera, sensor);
    stage.current?.reset(settings);
  }, [camera, sensor, settings]);
  const togglePaused = useCallback((): void => {
    setInputs(new Map());
    setPaused((current) => !current);
  }, []);
  useEffect(() => {
    const previousTitle = document.title;
    document.title = "Physics lab · Mirae";
    const reset = (): void => {
      setInputs(new Map());
    };
    const hidden = (): void => {
      if (document.hidden) reset();
    };
    const down = (event: KeyboardEvent): void => {
      if (
        event.target instanceof HTMLElement &&
        event.target.closest("input, textarea, select, [contenteditable=true]")
      )
        return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (ready && ["Space", "KeyN", "KeyR"].includes(event.code)) {
        if (event.code === "Space" && event.target instanceof HTMLElement && event.target.closest("button, summary"))
          return;
        event.preventDefault();
        if (event.repeat) return;
        if (event.code === "Space") togglePaused();
        if (event.code === "KeyN" && paused) stage.current?.stepOnce();
        if (event.code === "KeyR") resetExperiment();
        return;
      }
      const action = DRIVE_KEYS[event.code];
      if (!action) return;
      event.preventDefault();
      if (!event.repeat) changeInput(event.code, action);
    };
    const up = (event: KeyboardEvent): void => {
      if (DRIVE_KEYS[event.code]) changeInput(event.code);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", reset);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      document.title = previousTitle;
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", reset);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [changeInput, ready, paused, resetExperiment, togglePaused]);

  return (
    <>
      <SkipLink />
      <Header />
      <main id="main" tabIndex={-1} className="physics-page">
        <h1 className="sr-only">Physics lab</h1>
        <div className="physics-viewport" ref={viewport}>
          <canvas
            ref={canvas}
            tabIndex={0}
            aria-label="Interactive 3D physics environment with the actual Mirae model in a two-room flat. Drag to orbit; scroll to zoom."
          />
          {!ready || error ? (
            <div className="physics-loading" role="status">
              {error || "Loading the robot, the flat and physics…"}
            </div>
          ) : null}
          <details className="physics-settings" open={window.innerWidth > 600}>
            <summary>Experiment settings</summary>
            <div className="physics-setting-fields">
              {PARAMETERS.map(({ key, label, min, max, step, unit }) => (
                <label key={key}>
                  <span>
                    {label}
                    <output htmlFor={`physics-${key}`}>
                      {settings[key]}
                      {unit}
                    </output>
                  </span>
                  <input
                    id={`physics-${key}`}
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={settings[key]}
                    disabled={!ready}
                    onChange={(event) => {
                      const next = { ...settings, [key]: Number(event.target.value) };
                      setSettings(next);
                      setInputs(new Map());
                      stage.current?.setInput({ left: 0, right: 0 }, camera, sensor);
                      stage.current?.reset(next);
                    }}
                  />
                </label>
              ))}
              <label className="physics-toggle">
                <input
                  type="checkbox"
                  checked={showSupport}
                  onChange={(event) => {
                    setShowSupport(event.target.checked);
                  }}
                />
                Support triangle
              </label>
              <div className="physics-peripherals">
                <button
                  type="button"
                  aria-pressed={camera}
                  onClick={() => {
                    setCamera(!camera);
                  }}
                >
                  Camera
                </button>
                <button
                  type="button"
                  aria-pressed={sensor}
                  onClick={() => {
                    setSensor(!sensor);
                  }}
                >
                  ToF sensor
                </button>
              </div>
              <p>Changing a setting restarts the experiment.</p>
            </div>
          </details>
          <div className="physics-huds">
            <ComponentHud
              drive={drive}
              open={huds.components}
              onToggle={(open) => {
                setHuds((current) => ({ ...current, components: open }));
              }}
            />
            <details
              className="first-person-hud"
              open={huds.firstPerson}
              onToggle={(event) => {
                const open = event.currentTarget.open;
                setHuds((current) => ({ ...current, firstPerson: open }));
              }}
            >
              <summary className="hud-heading">
                <span>FIRST PERSON</span>
                <span>CAMERA</span>
              </summary>
              <div
                className="hud-render-area first-person-view"
                role="img"
                aria-label="Live first-person view from Mirae's CAD camera position"
              >
                <canvas />
              </div>
              <p>Robot camera · follows pitch & roll</p>
            </details>
          </div>
          <div className="physics-telemetry" aria-label="Live physics measurements">
            <div>
              <span>SPEED</span>
              <strong data-testid="speed">
                {(telemetry?.speed ?? 0).toFixed(2)} <small>m/s</small>
              </strong>
            </div>
            <div>
              <span>ACCEL.</span>
              <strong>
                {(telemetry?.acceleration ?? 0).toFixed(2)} <small>m/s²</small>
              </strong>
            </div>
            <div>
              <span>PITCH / ROLL</span>
              <strong>
                {(telemetry?.pitch ?? 0).toFixed(1)}° / {(telemetry?.roll ?? 0).toFixed(1)}°
              </strong>
            </div>
            <div className="physics-contacts">
              <span>GROUND CONTACT</span>
              <strong>
                {["L", "R", "Caster"].map((label, i) => (
                  <small key={label} className={telemetry?.contacts[i] ? "contact-on" : "contact-off"}>
                    {label} {telemetry?.contacts[i] ? "●" : "○"}
                  </small>
                ))}
              </strong>
            </div>
          </div>
          <div className="physics-drive">
            <div className="physics-shortcuts" aria-label="Simulation shortcuts">
              <button type="button" aria-keyshortcuts="Space" disabled={!ready} onClick={togglePaused}>
                <kbd>Space</kbd> {paused ? "Resume" : "Pause"}
              </button>
              <button
                type="button"
                aria-keyshortcuts="N"
                disabled={!ready || !paused}
                onClick={() => {
                  stage.current?.stepOnce();
                }}
              >
                <kbd>N</kbd> Step
              </button>
              <button type="button" aria-keyshortcuts="R" disabled={!ready} onClick={resetExperiment}>
                <kbd>R</kbd> Reset
              </button>
            </div>
            <div className="drive-pad" aria-label="Drive controls">
              {CONTROLS.map(({ action, label, key, arrow }) => (
                <button
                  key={action}
                  type="button"
                  disabled={!ready || paused}
                  className={cx("drive-key", `drive-key-${action}`, actions.has(action) && "is-active")}
                  aria-label={label}
                  onPointerDown={(event) => {
                    if (event.button !== 0) return;
                    event.currentTarget.setPointerCapture(event.pointerId);
                    changeInput(`pointer-${event.pointerId}`, action);
                  }}
                  onPointerUp={(event) => {
                    changeInput(`pointer-${event.pointerId}`);
                  }}
                  onPointerCancel={(event) => {
                    changeInput(`pointer-${event.pointerId}`);
                  }}
                  onLostPointerCapture={(event) => {
                    changeInput(`pointer-${event.pointerId}`);
                  }}
                  onKeyDown={(event) => {
                    if (event.code === "Space" || event.code === "Enter") {
                      event.preventDefault();
                      changeInput(`button-${key}`, action);
                    }
                  }}
                  onKeyUp={(event) => {
                    if (event.code === "Space" || event.code === "Enter") {
                      event.preventDefault();
                      changeInput(`button-${key}`);
                    }
                  }}
                  onBlur={() => {
                    changeInput(`button-${key}`);
                  }}
                >
                  <span aria-hidden="true">{arrow}</span>
                  <small>{key}</small>
                </button>
              ))}
            </div>
            <p>WASD / arrows · release to brake</p>
          </div>
          <span className="physics-orbit-hint">Drag to orbit · Scroll to zoom</span>
        </div>
        <footer className="physics-footnote">
          <span>CAD geometry · {Math.round(telemetry?.wheelbase ?? 97)} mm wheelbase · 1.727 kg estimated</span>
          <details>
            <summary>Model assumptions</summary>
            <p>
              Real gravity, motor-driven wheel joints, friction and a free-rolling ball caster. Default CoM: 36 mm ahead
              of axle, 60 mm high, from the documented mass budget. Collision hulls and box inertia are approximations;
              friction and torque limits are adjustable. Camera and sensor buttons preview highlights only. This model
              needs validation against the assembled robot. The flat (16 m² living room, 12 m² bedroom) uses typical
              retail furniture sizes, not a measured home; its colliders are boxes and cylinders, and slopes tilt the
              whole flat.
            </p>
          </details>
        </footer>
      </main>
    </>
  );
}
