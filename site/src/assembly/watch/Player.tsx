import type { CSSProperties } from "react";

import { cx } from "../../lib";
import { buttonClass, label } from "../../ui";
import { STAGES, STEPS } from "../steps";
import { clock, type Speed, SPEEDS } from "./timing";

interface PlayerProps {
  index: number;
  playing: boolean;
  speed: Speed;
  captions: boolean;
  /** Length of the current step at the current speed: the current chapter fills over it. */
  currentMs: number;
  starts: readonly number[];
  total: number;
  onGo: (i: number) => void;
  onPlaying: (playing: boolean) => void;
  onSpeed: (speed: Speed) => void;
  onCaptions: (on: boolean) => void;
  onFullscreen: () => void;
}

const SMALL = buttonClass("line", true);

/** The watch-mode bar: one chapter per step, grouped by stage, and the transport controls. */
export function Player(p: PlayerProps) {
  const last = STEPS.length - 1;
  return (
    <div className="grid gap-2.5 rounded-card-lg bg-surface px-5 pt-3.5 pb-3 [box-shadow:0_0_0_1px_var(--color-line)]">
      <div className="flex gap-2" aria-hidden="true">
        {STAGES.map((st) => {
          const n = STEPS.filter((s) => s.stage === st.id).length;
          return (
            <span key={st.id} className={cx(label, "tracking-[0.14em] text-mute")} style={{ flex: n }}>
              {st.label}
            </span>
          );
        })}
      </div>
      <ol className="flex h-6 items-center gap-2" aria-label="Chapters">
        {STAGES.map((st) => (
          <li key={st.id} className="flex gap-[3px]" style={{ flex: STEPS.filter((s) => s.stage === st.id).length }}>
            {STEPS.map((s, i) =>
              s.stage !== st.id ? null : (
                <button
                  key={s.id}
                  type="button"
                  title={`${i + 1}. ${s.title}`}
                  aria-label={`Step ${i + 1}: ${s.title}`}
                  aria-current={i === p.index ? "step" : undefined}
                  onClick={() => p.onGo(i)}
                  className="group relative h-6 flex-1 cursor-pointer border-0 bg-transparent p-0"
                >
                  <span
                    className={cx(
                      "absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 overflow-hidden rounded-[3px] transition-[height] group-hover:h-3",
                      i < p.index ? "bg-ink" : "bg-sunk",
                      i === p.index && "h-3",
                    )}
                  >
                    {i === p.index && (
                      <span
                        key={`${p.index}-${p.speed}`}
                        className="block h-full animate-[watch-fill_var(--d)_linear_forwards] bg-accent"
                        style={
                          {
                            "--d": `${p.currentMs}ms`,
                            animationPlayState: p.playing ? "running" : "paused",
                          } as CSSProperties
                        }
                      />
                    )}
                  </span>
                </button>
              ),
            )}
          </li>
        ))}
      </ol>
      <div className="flex items-center gap-2.5">
        <button className={SMALL} type="button" disabled={p.index === 0} onClick={() => p.onGo(p.index - 1)}>
          Previous
        </button>
        <button
          className={cx(buttonClass("dark", true), "min-w-[88px]")}
          type="button"
          onClick={() => p.onPlaying(!p.playing)}
        >
          {p.playing ? "Pause" : "Play"}
        </button>
        <button className={SMALL} type="button" disabled={p.index === last} onClick={() => p.onGo(p.index + 1)}>
          Next
        </button>
        <span className="ml-2 font-mono text-[12px] text-ink-2">
          {clock((p.starts[p.index] ?? 0) / p.speed)} / {clock(p.total / p.speed)}
        </span>
        <span className="flex-1" />
        <button className={SMALL} type="button" aria-pressed={p.captions} onClick={() => p.onCaptions(!p.captions)}>
          Captions {p.captions ? "on" : "off"}
        </button>
        <button
          className={SMALL}
          type="button"
          onClick={() => p.onSpeed(SPEEDS[(SPEEDS.indexOf(p.speed) + 1) % SPEEDS.length] ?? 1)}
        >
          Speed {p.speed}×
        </button>
        <button className={SMALL} type="button" onClick={p.onFullscreen}>
          Full screen
        </button>
      </div>
    </div>
  );
}
