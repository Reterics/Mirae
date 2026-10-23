import { useEffect, useRef, useState } from "react";

import { cx, media, reducedMotion } from "../../lib";
import { buttonClass, textLink } from "../../ui";
import { FIGURE } from "./figure";
import { PI_STEPS } from "./model";
import type { AssemblyStage, Projected } from "./stage";

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const SCRUB_STEPS = 100;

/**
 * The step in 3D: the new part slides into place when the step opens; drag to look around, the
 * slider scrubs the insertion. Mount it once per page (not per step): it owns the page's only
 * WebGL context. three.js is shared with the homepage turntable and loaded on demand. Until the
 * model has loaded, and wherever WebGL fails, the step's rendered poster shows instead.
 */
export function StepViewer({
  id,
  label,
  poster,
  watch,
}: {
  id: string;
  label?: string | undefined;
  /** Shown until the model has loaded, and instead of it if WebGL or the download fails. */
  poster?: string | undefined;
  /** Watch mode: glide the camera in from the last step, play slower, no per-step controls. */
  watch?: { glideMs: number; playMs: number } | undefined;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stage, setStage] = useState<AssemblyStage | null>(null);
  const [view, setView] = useState<Projected | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let live = true;
    let made: AssemblyStage | undefined;
    import("./stage")
      .then(({ AssemblyStage }) => {
        if (!live) return;
        made = new AssemblyStage(canvas);
        made.onFrame = setView;
        return made.ready.then(() => {
          // only now: a step shown before the model arrives would play against an empty scene
          if (live && made) setStage(made);
        });
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
      made?.destroy();
    };
  }, []);

  const glideMs = watch?.glideMs ?? 0;
  const playMs = watch?.playMs ?? 1400;
  useEffect(() => {
    if (!stage) return;
    if (reducedMotion) {
      stage.show(id, 1);
      return;
    }
    stage.show(id, 0, glideMs);
    stage.play(playMs, glideMs);
  }, [stage, id, glideMs, playMs]);

  const k = view?.k ?? 0;
  const [ax, ay] = view?.at ?? [0, 0];
  const [sx, sy] = view?.seat ?? [0, 0];

  return (
    <figure className={FIGURE.frame}>
      <div className={FIGURE.stage}>
        {poster && !stage && <img className={cx(FIGURE.layer, "object-contain")} src={poster} alt="" />}
        <canvas
          ref={canvasRef}
          className={cx(FIGURE.layer, "cursor-grab")}
          hidden={failed}
          role="img"
          aria-label={label ? `${label} moving into place; drag to turn` : ""}
        />
        {view && (
          <svg
            className={cx(FIGURE.layer, "pointer-events-none")}
            viewBox="0 0 1000 750"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <marker
                id="step-arrow"
                viewBox="0 0 10 10"
                refX="5"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto"
              >
                <path className={FIGURE.arrowHead} d="M0 0 10 5 0 10z" />
              </marker>
            </defs>
            <line
              className={cx(FIGURE.arrow, k >= 1 && "opacity-0")}
              x1={lerp(ax, sx, 0.3) * 1000}
              y1={lerp(ay, sy, 0.3) * 750}
              x2={lerp(ax, sx, 0.85) * 1000}
              y2={lerp(ay, sy, 0.85) * 750}
              markerEnd="url(#step-arrow)"
            />
          </svg>
        )}
        {label && view && (
          <span className={FIGURE.label} style={{ left: `${ax * 100}%`, top: `${ay * 100}%` }}>
            {label}
          </span>
        )}
      </div>
      <div className={FIGURE.controls} hidden={failed || watch !== undefined}>
        <button className={buttonClass("line", true)} type="button" disabled={!stage} onClick={() => stage?.play()}>
          Replay
        </button>
        <input
          className={FIGURE.scrub}
          type="range"
          min={0}
          max={SCRUB_STEPS}
          value={Math.round(k * SCRUB_STEPS)}
          onChange={(e) => stage?.setProgress(Number(e.target.value) / SCRUB_STEPS)}
          disabled={!stage}
          aria-label="Scrub the step animation"
        />
        <button
          className={buttonClass("line", true)}
          type="button"
          disabled={!stage}
          onClick={() => stage?.resetView()}
        >
          Reset view
        </button>
      </div>
      {PI_STEPS.has(id) && (
        <figcaption className="px-1 pt-2 text-[12px] leading-[1.4] text-mute">
          Raspberry Pi 5 model © Raspberry Pi Ltd,{" "}
          <a className={textLink} href={media("assembly/LICENSE-raspberry-pi-5-model.txt")}>
            MIT licence
          </a>
          , simplified for this page.
        </figcaption>
      )}
    </figure>
  );
}
