import { type ComponentType, useEffect, useLayoutEffect, useRef } from "react";

import { cx } from "../../lib";
import { buttonClass } from "../../ui";
import { FIGURE } from "../viewer/figure";
import { WiringDiagram } from "./WiringDiagram";

export interface DiagramProps {
  watch?: { durationMs: number; playing: boolean } | undefined;
}

/**
 * The wiring diagram in a step's figure: fitted to the panel, and opened at full size in a scrolling
 * dialog on click, since a sheet with every wire drawn is too dense to read at panel size.
 */
export function WiringFigure({
  Diagram = WiringDiagram,
  label = "Wiring diagram",
  watch,
}: DiagramProps & {
  Diagram?: ComponentType<{ className: string }>;
  label?: string;
} = {}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const pan = useRef<Animation | null>(null);
  const duration = watch?.durationMs;
  const playing = watch?.playing ?? false;
  useLayoutEffect(() => {
    const frame = viewport.current;
    const content = sheet.current;
    if (!frame || !content || duration === undefined) return;
    const resize = () => {
      const elapsed = Number(pan.current?.currentTime ?? 0);
      const paused = pan.current?.playState === "paused";
      pan.current?.cancel();
      const travel = Math.max(0, content.offsetHeight - frame.clientHeight);
      pan.current = content.animate(
        [
          { transform: "translateY(0)", offset: 0 },
          { transform: "translateY(0)", offset: 0.1 },
          { transform: `translateY(-${travel}px)`, offset: 0.9 },
          { transform: `translateY(-${travel}px)`, offset: 1 },
        ],
        { duration, fill: "both", easing: "linear" },
      );
      pan.current.currentTime = elapsed;
      if (paused) pan.current.pause();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(frame);
    observer.observe(content);
    return () => {
      observer.disconnect();
      pan.current?.cancel();
      pan.current = null;
    };
  }, [Diagram, duration]);
  useEffect(() => {
    if (playing) pan.current?.play();
    else pan.current?.pause();
  }, [playing, duration]);
  const open = () => dialog.current?.showModal();
  if (watch) {
    return (
      <div ref={viewport} className={cx(FIGURE.layer, "overflow-hidden")}>
        <div ref={sheet}>
          <Diagram className="block h-auto w-full" />
        </div>
      </div>
    );
  }
  return (
    <>
      <button
        type="button"
        className={cx(FIGURE.layer, "cursor-zoom-in border-0 bg-transparent p-0")}
        onClick={open}
        aria-label={`Open the ${label.toLowerCase()} at full size`}
      >
        <Diagram className={FIGURE.layer} />
      </button>
      {/* below the stage on narrow screens (the frame leaves room), where it would cover the sheet */}
      <button
        type="button"
        className={cx(
          buttonClass("light", true),
          "absolute right-3 bottom-3 max-960:inset-x-0 max-960:top-[calc(100%+8px)] max-960:bottom-auto max-960:[box-shadow:0_0_0_1px_var(--color-line)]",
        )}
        onClick={open}
      >
        Open full size
      </button>
      <dialog
        ref={dialog}
        className="m-0 h-dvh max-h-none w-dvw max-w-none overflow-auto border-0 bg-surface p-0 backdrop:bg-ink/40"
        aria-label={label}
        onClick={(e) => {
          if (e.target === e.currentTarget) e.currentTarget.close();
        }}
      >
        <div className="sticky top-0 z-10 flex justify-end bg-surface/90 p-3">
          <button type="button" className={buttonClass("dark", true)} onClick={() => dialog.current?.close()}>
            Close
          </button>
        </div>
        <div className="px-4 pb-8">
          <Diagram className="mx-auto block h-auto w-[1420px] max-w-none" />
        </div>
      </dialog>
    </>
  );
}
