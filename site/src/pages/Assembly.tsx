import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useLocation, useNavigate } from "react-router";

import { STAGES, STEPS, stepIndex } from "../assembly/steps";
import { ShoppingCart } from "../assembly/ShoppingCart";
import { FIGURE } from "../assembly/viewer/figure";
import { MODEL_STEPS, STILL_STEPS } from "../assembly/viewer/model";
import { Player } from "../assembly/watch/Player";
import { GLIDE_MS, INSERT_MS, type Speed, stepMs, timeline } from "../assembly/watch/timing";
import { PowerChain } from "../assembly/wiring/Diagrams";
import { type DiagramProps, WiringFigure } from "../assembly/wiring/WiringFigure";
import { StepViewer } from "../assembly/viewer/StepViewer";
import { Link } from "../components/Link";
import { SkipLink } from "../components/SkipLink";
import { cx, media } from "../lib";
import { Footer } from "../sections/Footer";
import { Header } from "../sections/Header";
import { LINKS, SITE } from "../site";
import { buttonClass, eyebrow, eyebrowDot, label, textLink } from "../ui";

const DONE_KEY = "mirae.assembly.done";
/** Steps whose figure is a wiring diagram (from docs/wiring.md) rather than the 3D model or a render. */
const DIAGRAMS: Partial<Record<string, React.ComponentType<DiagramProps>>> = {
  "wire-base": PowerChain,
  cables: WiringFigure,
};
const DIAGRAM_STEPS: ReadonlySet<string> = new Set(Object.keys(DIAGRAMS));
const TIMELINE = timeline(DIAGRAM_STEPS);
/** The segmented Step by step / Watch all switch at the top of the step list. */
const modeButton = (on: boolean): string =>
  cx(
    "h-8 flex-1 cursor-pointer rounded-full border-0 font-sans text-[13px] font-medium transition-colors",
    on ? "bg-surface text-ink [box-shadow:0_1px_2px_rgb(0_0_0/0.08)]" : "bg-transparent text-ink-2 hover:text-ink",
  );

const SUBHEAD = cx(label, "mb-3 tracking-[0.18em] text-mute");
const NOTE = "mt-5 rounded-[14px] px-4 py-3 text-[14px] leading-[1.55] text-ink-2";
const SURFACE = "rounded-card-lg bg-surface [box-shadow:0_0_0_1px_var(--color-line)]";
/** The step list: a panel of its own height that scrolls inside, so the page doesn't have to. */
const RAIL = cx(SURFACE, "flex min-h-0 flex-col overflow-hidden max-960:bg-transparent max-960:[box-shadow:none]");
/** You'll need / Do this: scrolls inside when a step's text is longer than the screen. */
const PANEL = cx(
  SURFACE,
  "min-h-0 [scrollbar-width:thin] overflow-y-auto px-6 py-5 max-960:overflow-visible max-960:p-5",
);
const PAGER = "disabled:pointer-events-none disabled:opacity-40";
/** Numbered instruction: the number sits in a tinted circle in the left margin. */
const INSTRUCTION = cx(
  "relative pl-9 [counter-increment:do]",
  "before:absolute before:top-0.5 before:left-0 before:grid before:size-6 before:place-items-center before:rounded-[50%] before:bg-sunk",
  "before:font-mono before:text-[12px] before:leading-none before:font-medium before:content-[counter(do)]",
);

/** A step in the list; below 960px only its number shows (font-size 0 hides the title). */
const stepLink = (current: boolean): string =>
  cx(
    "flex items-baseline gap-3 rounded-xl px-2.5 py-[7px] text-[14px] leading-[1.35] [transition:background-color_0.2s] max-960:p-1 max-960:text-[0px]",
    current
      ? "bg-sunk text-ink max-960:bg-surface max-960:[box-shadow:0_0_0_1px_var(--color-line)]"
      : "text-ink-2 hover:bg-sunk",
  );

const stepNumber = (current: boolean, done: boolean): string =>
  cx(
    "inline-grid size-6 flex-none place-items-center rounded-[50%] border font-mono text-[12px] leading-none font-medium",
    done ? "border-ink bg-ink text-bg" : current ? "border-accent text-accent-ink" : "border-line-strong text-mute",
  );

/** The honesty note: in the step list on desktop, under the step on narrow screens. */
function Untested({ className }: { className: string }) {
  return (
    <p className={cx("flex gap-2.5 text-[13px] leading-[1.45] text-ink-2", className)}>
      <span className={cx(eyebrowDot, "mt-1.5 flex-none")} aria-hidden="true" />
      <span>
        Not yet tested on a physical robot. The steps come from the CAD model; check each fit before you force anything,
        and{" "}
        <Link className={textLink} href={`${LINKS.repo}/issues`}>
          tell us
        </Link>{" "}
        what didn&apos;t match.
      </span>
    </p>
  );
}

/** Ticked steps, remembered in this browser only (it may be unavailable: private mode, previews). */
function useDone(): [ReadonlySet<string>, (id: string) => void] {
  const [done, setDone] = useState<ReadonlySet<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(DONE_KEY) ?? "[]") as string[]);
    } catch {
      return new Set();
    }
  });
  const toggle = useCallback((id: string) => {
    setDone((cur) => {
      const next = new Set(cur);
      if (!next.delete(id)) next.add(id);
      try {
        localStorage.setItem(DONE_KEY, JSON.stringify([...next]));
      } catch {
        // not persisted; the ticks still work for this visit
      }
      return next;
    });
  }, []);
  return [done, toggle];
}

export function Assembly() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const [done, toggleDone] = useDone();
  // The 3D figure mounts on the first step that has one and then stays, hidden on steps without
  // one: it holds the page's only WebGL context and the loaded model.
  const [viewer, setViewer] = useState(false);
  // Watch all: the same steps played as one tutorial; the list and the timeline still jump around.
  const [watch, setWatch] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [captions, setCaptions] = useState(true);
  const articleRef = useRef<HTMLElement>(null);

  const index = Math.max(0, stepIndex(hash.slice(1)));
  const step = STEPS[index];
  const go = useCallback(
    (i: number) => {
      const target = STEPS[i];
      if (target) void navigate({ hash: `#${target.id}` });
    },
    [navigate],
  );

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Keep the current step in view inside the list, scrolling only the list (never the page).
  const listRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const list = listRef.current;
    const current = list?.querySelector<HTMLElement>('[aria-current="step"]');
    if (!list || !current) return;
    const box = list.getBoundingClientRect();
    const at = current.getBoundingClientRect();
    const pad = 48; // keep a neighbour or the stage name visible
    if (at.top < box.top + pad) list.scrollTop -= box.top + pad - at.top;
    else if (at.bottom > box.bottom - pad) list.scrollTop += at.bottom - (box.bottom - pad);
    if (at.left < box.left || at.right > box.right) list.scrollLeft += at.left - box.left - pad; // narrow: a row
  }, [index]);

  // ← / → move between steps, unless a control (like the scrub slider) wants the keys; in watch
  // mode the space bar plays and pauses.
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (document.querySelector("dialog[open]")) return;
      if (e.target instanceof HTMLInputElement || e.altKey || e.metaKey || e.ctrlKey) return;
      if (e.key === "ArrowRight") go(index + 1);
      if (e.key === "ArrowLeft") go(index - 1);
      if (e.key === " " && watch && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault();
        setPlaying((on) => !on);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, index, watch]);

  // Watch mode's clock: each step runs for its length, then the next one opens. Pausing keeps
  // what's left of the step; opening a step (list, timeline, keys) starts it from the top.
  const remaining = useRef(0);
  const startedAt = useRef(0);
  const current = STEPS[index];
  const currentMs = current ? stepMs(current, DIAGRAM_STEPS) / speed : 0;
  useEffect(() => {
    remaining.current = currentMs;
  }, [watch, index, currentMs]);
  useEffect(() => {
    if (!watch || !playing) return;
    startedAt.current = performance.now();
    const timer = window.setTimeout(() => {
      remaining.current = 0;
      if (index < STEPS.length - 1) go(index + 1);
      else setPlaying(false);
    }, remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current = Math.max(0, remaining.current - (performance.now() - startedAt.current));
    };
  }, [watch, playing, index, go, currentMs]);

  const fullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void articleRef.current?.requestFullscreen();
  }, []);

  const inModel = step !== undefined && MODEL_STEPS.has(step.id);
  const still = step !== undefined && STILL_STEPS.has(step.id);
  const Diagram = step && DIAGRAMS[step.id];
  // adjusting state while rendering, as React recommends; watch mode loads the model up front
  if ((inModel || watch) && !viewer) setViewer(true);

  if (!step) return null;
  const prev = STEPS[index - 1];
  const next = STEPS[index + 1];

  const stage = STAGES.find((st) => st.id === step.stage);

  return (
    <>
      <title>{`Assembly guide · ${SITE.name}`}</title>
      <SkipLink />
      <Header />
      {/* One screen on desktop: the step list and the instructions scroll inside their own panels,
          so the figure and Back / Next never leave the view. Wider than the site's wrap so the figure
          isn't a tall sliver on big screens. Narrow screens scroll as a page. */}
      <main
        id="main"
        className="mx-auto grid h-dvh min-h-[640px] w-full max-w-[1760px] grid-cols-[300px_minmax(0,1fr)] gap-7 px-(--gutter) pt-[calc(var(--header-h)+16px)] pb-6 max-960:h-auto max-960:min-h-0 max-960:grid-cols-[minmax(0,1fr)] max-960:gap-6 max-960:pb-16"
      >
        <aside className={RAIL}>
          <div className="border-b border-b-line px-5 py-4 max-960:border-0 max-960:px-0 max-960:pt-0">
            <ShoppingCart onOpen={() => setPlaying(false)} />
          </div>
          <div className="grid gap-3 border-b border-b-line px-5 pt-5 pb-4 max-960:hidden">
            <p className={cx(eyebrow, "text-mute")}>Assembly guide</p>
            <div className="flex rounded-full bg-sunk p-[3px]" role="group" aria-label="Mode">
              <button
                className={modeButton(!watch)}
                type="button"
                aria-pressed={!watch}
                onClick={() => {
                  setWatch(false);
                  setPlaying(false);
                }}
              >
                Step by step
              </button>
              <button
                className={modeButton(watch)}
                type="button"
                aria-pressed={watch}
                onClick={() => {
                  setWatch(true);
                  setPlaying(true);
                }}
              >
                Watch all
              </button>
            </div>
            <p className="flex justify-between text-[14px] text-ink-2">
              <span>
                {done.size} of {STEPS.length} done
              </span>
              <span className="text-mute">saved in this browser</span>
            </p>
            <div className="h-1 overflow-hidden rounded-full bg-sunk" aria-hidden="true">
              <div className="h-full bg-ink" style={{ width: `${(done.size / STEPS.length) * 100}%` }} />
            </div>
          </div>
          {/* on narrow screens the list is a scrolling row of numbers grouped under their stage names; the
              current title is right below */}
          <nav
            ref={listRef}
            className="min-h-0 flex-1 [scrollbar-width:thin] overflow-y-auto px-2.5 pt-2 pb-4 max-960:flex max-960:gap-1.5 max-960:overflow-x-auto max-960:overflow-y-visible max-960:p-0 max-960:pb-1.5"
            aria-label="Steps"
          >
            {STAGES.map((st) => {
              const steps = STEPS.filter((s) => s.stage === st.id);
              if (steps.length === 0) return null;
              return (
                <div key={st.id} className="max-960:flex max-960:flex-none max-960:items-center max-960:gap-1.5">
                  <p
                    className={cx(
                      label,
                      "mx-2 mt-3 mb-1.5 tracking-[0.18em] text-mute max-960:my-0 max-960:mr-0 max-960:ml-2 max-960:text-[11px] max-960:whitespace-nowrap",
                    )}
                  >
                    {st.label}
                  </p>
                  <ol className="max-960:flex max-960:gap-1.5">
                    {steps.map((s) => (
                      <li key={s.id}>
                        <RouterLink
                          to={{ hash: `#${s.id}` }}
                          className={stepLink(s.id === step.id)}
                          aria-current={s.id === step.id ? "step" : undefined}
                        >
                          <span className={stepNumber(s.id === step.id, done.has(s.id))}>{stepIndex(s.id) + 1}</span>
                          {s.title}
                        </RouterLink>
                      </li>
                    ))}
                  </ol>
                </div>
              );
            })}
          </nav>
          <Untested className="border-t border-t-line px-5 py-3.5 max-960:hidden" />
        </aside>

        <article
          ref={articleRef}
          className={cx(
            "grid min-h-0 gap-4 bg-bg max-960:grid-rows-none [&:fullscreen]:p-6",
            // watch mode: the title is only for screen readers (the caption shows it), so two rows
            watch ? "grid-rows-[minmax(0,1fr)_auto]" : "grid-rows-[auto_minmax(0,1fr)_auto]",
          )}
          aria-labelledby="step-title"
        >
          <div className={cx("flex items-end justify-between gap-6", watch && "sr-only")}>
            <div>
              <p className={cx(label, "tracking-[0.18em] text-accent-ink")}>
                {stage?.label} · Step {index + 1} of {STEPS.length}
              </p>
              <h1 className="mt-2 text-[length:clamp(26px,2.4vw,34px)] leading-[1.15]" id="step-title">
                {step.title}
              </h1>
            </div>
            <p className="flex-none pb-1 font-mono text-[11px] text-mute max-960:hidden">← → move between steps</p>
          </div>

          <div
            className={cx(
              "relative grid min-h-0 gap-5 max-960:grid-cols-[minmax(0,1fr)]",
              watch
                ? cx("grid-cols-[minmax(0,1fr)]", !!Diagram && captions && "grid-rows-[minmax(0,1fr)_auto]")
                : inModel || still || Diagram
                  ? "grid-cols-[minmax(0,1.45fr)_minmax(320px,1fr)]"
                  : "grid-cols-[minmax(0,1fr)]",
            )}
          >
            {/* mounted on the first step with a model, then kept (hidden) for the page's only WebGL context */}
            {viewer && (
              <div hidden={!inModel} className="min-h-0">
                <StepViewer
                  id={step.id}
                  label={step.label}
                  poster={media(`assembly/${step.id}.webp`)}
                  watch={watch ? { glideMs: GLIDE_MS / speed, playMs: INSERT_MS / speed } : undefined}
                />
              </div>
            )}
            {still && (
              <figure className={FIGURE.frame}>
                <div className={FIGURE.stage}>
                  <img className={cx(FIGURE.layer, "object-contain")} src={media(`assembly/${step.id}.webp`)} alt="" />
                </div>
              </figure>
            )}
            {Diagram && (
              <figure className={cx(FIGURE.frame, !watch && "max-960:pb-[54px]")}>
                <div className={FIGURE.stage}>
                  <Diagram watch={watch ? { durationMs: currentMs, playing } : undefined} />
                </div>
              </figure>
            )}
            {watch && captions && (
              <div
                className={cx(
                  "pointer-events-none flex items-end justify-between gap-6",
                  Diagram ? "px-1" : "absolute inset-x-6 bottom-11",
                )}
              >
                <div
                  className="pointer-events-auto max-w-[640px] rounded-2xl bg-ink/92 px-5 py-4 text-bg"
                  aria-live="polite"
                >
                  <p className={cx(label, "tracking-[0.16em] text-accent")}>
                    {stage?.label} · Step {index + 1} of {STEPS.length}
                  </p>
                  <p className="mt-1.5 text-[19px] leading-[1.25] font-medium">{step.title}</p>
                  <p className="mt-1.5 line-clamp-2 text-[14px] leading-[1.45] text-[#d9d2c7] [&_a]:border-white/50 [&_a]:text-bg [&_a:hover]:border-white">
                    {step.instructions[0]}
                  </p>
                </div>
                <button
                  className={cx(buttonClass("light", true), "pointer-events-auto")}
                  type="button"
                  onClick={() => {
                    setWatch(false);
                    setPlaying(false);
                  }}
                >
                  Open this step
                </button>
              </div>
            )}
            <div className={PANEL} hidden={watch}>
              <section aria-label="You'll need">
                <h2 className={SUBHEAD}>You&apos;ll need</h2>
                <ul className="mb-7 grid gap-2 text-[15px] leading-[1.4]">
                  {step.items.map(({ name, qty }) => (
                    <li key={name}>
                      {qty !== undefined && (
                        <b className="mr-2 font-mono text-[13px] leading-none font-medium">{qty}×</b>
                      )}
                      {name}
                    </li>
                  ))}
                </ul>
              </section>
              <section aria-label="Instructions">
                <h2 className={SUBHEAD}>Do this</h2>
                <ol className="grid gap-3 text-[16px] leading-[1.55] [counter-reset:do]">
                  {step.instructions.map((text, i) => (
                    <li key={i} className={INSTRUCTION}>
                      {text}
                    </li>
                  ))}
                </ol>
                {step.tip && <p className={cx(NOTE, "bg-sunk")}>{step.tip}</p>}
                {step.caution && <p className={cx(NOTE, "bg-[#fbe9d9]")}>{step.caution}</p>}
              </section>
            </div>
          </div>

          {watch && (
            <Player
              index={index}
              playing={playing}
              speed={speed}
              captions={captions}
              currentMs={currentMs}
              starts={TIMELINE.starts}
              total={TIMELINE.total}
              onGo={go}
              onPlaying={setPlaying}
              onSpeed={setSpeed}
              onCaptions={setCaptions}
              onFullscreen={fullscreen}
            />
          )}
          {/* narrow screens: pinned to the bottom of the screen, so Back / Next never needs a scroll */}
          <footer
            className="flex items-center justify-between gap-4 max-960:sticky max-960:bottom-0 max-960:z-10 max-960:-mx-(--gutter) max-960:border-t max-960:border-t-line max-960:bg-bg/95 max-960:px-(--gutter) max-960:py-3 max-960:[backdrop-filter:blur(10px)]"
            hidden={watch}
          >
            <label className="inline-flex cursor-pointer items-center gap-2.5 text-[15px]">
              <input
                className="size-[18px] accent-ink"
                type="checkbox"
                checked={done.has(step.id)}
                onChange={() => toggleDone(step.id)}
              />
              Done
            </label>
            <div className="flex gap-2.5">
              <button
                className={cx(buttonClass("line"), PAGER)}
                type="button"
                disabled={!prev}
                onClick={() => go(index - 1)}
              >
                Back
              </button>
              <button
                className={cx(buttonClass("dark"), PAGER)}
                type="button"
                disabled={!next}
                onClick={() => go(index + 1)}
              >
                Next step
              </button>
            </div>
          </footer>
          <Untested className="hidden max-960:flex" />
        </article>
      </main>
      <Footer />
    </>
  );
}
