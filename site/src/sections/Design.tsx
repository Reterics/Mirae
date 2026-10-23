import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef, useState } from "react";

import { SectionHead } from "../components/SectionHead";
import { CHAPTERS } from "../content";
import { cx, media, reducedMotion } from "../lib";
import type { Turntable } from "../turntable";
import { kicker } from "../ui";

/** Pinned stage where scrolling turns the model a full 360° and steps through the chapters. */
export function Design() {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fillRef = useRef<HTMLSpanElement>(null);
  const turnRef = useRef<Turntable | null>(null);
  const progressRef = useRef(0);
  const [ready, setReady] = useState(false);
  const [chapter, setChapter] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const section = sectionRef.current;
    if (!canvas || !section || reducedMotion) return;
    let live = true;
    let made: Turntable | undefined;
    // Keep Three.js and the model off the initial page load.
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        import("../turntable")
          .then(({ Turntable }) => {
            if (!live) return;
            made = new Turntable(canvas);
            turnRef.current = made;
            made.show(progressRef.current);
            return made.ready.then(() => {
              if (live) setReady(true);
            });
          })
          .catch(() => {
            made?.destroy();
            if (live) turnRef.current = null;
          });
      },
      { rootMargin: "600px" },
    );
    observer.observe(section);
    const lost = (): void => setReady(false);
    canvas.addEventListener("webglcontextlost", lost);
    return () => {
      live = false;
      observer.disconnect();
      canvas.removeEventListener("webglcontextlost", lost);
      made?.destroy();
      turnRef.current = null;
    };
  }, []);

  useGSAP(() => {
    ScrollTrigger.create({
      trigger: sectionRef.current,
      start: "top top",
      end: "bottom bottom",
      scrub: !reducedMotion,
      onUpdate: ({ progress }) => {
        progressRef.current = progress;
        turnRef.current?.show(progress);
        setChapter(Math.min(CHAPTERS.length - 1, Math.floor(progress * CHAPTERS.length)));
        if (fillRef.current) fillRef.current.style.transform = `scaleX(${progress})`;
      },
    });
  });

  return (
    <section
      ref={sectionRef}
      className="relative h-[300vh] border-t border-t-line"
      id="design"
      aria-labelledby="design-title"
    >
      <div className="sticky top-0 h-svh overflow-hidden pt-(--header-h)">
        <div
          className={cx(
            "wrap grid h-full grid-cols-[minmax(0,440px)_minmax(0,1fr)] grid-rows-[auto_1fr_auto] gap-x-[clamp(24px,4vw,64px)] pt-[clamp(28px,5vh,56px)] pb-7",
            // one column: title, model, chapter, progress
            "max-960:grid-cols-1 max-960:grid-rows-[auto_minmax(0,1fr)_auto_auto] max-960:gap-y-3",
          )}
        >
          <SectionHead
            className="col-1 row-1 grid gap-[18px]"
            eyebrowClassName="max-560:hidden"
            titleClassName="max-960:text-[32px] max-560:text-[28px]"
            reveal={false}
            id="design-title"
            eyebrow="Design"
            title="Every angle,"
            muted="from the real model."
          />

          <div
            className="col-1 row-2 grid self-center max-960:row-3 max-960:min-h-[150px] max-960:self-start"
            aria-live="polite"
          >
            {CHAPTERS.map(({ label, title, body }, i) => (
              <article
                key={label}
                className={cx(
                  "[grid-area:1/1] [transition:opacity_0.5s_var(--ease),transform_0.7s_var(--ease)]",
                  i === chapter
                    ? "visible [transform:none] opacity-100"
                    : "invisible [transform:translateY(18px)] opacity-0",
                )}
              >
                <p className={kicker}>
                  {String(i + 1).padStart(2, "0")} · {label}
                </p>
                <h3 className="mt-4 mb-3.5 text-[length:clamp(28px,2.6vw,40px)] max-560:mt-2.5 max-560:mb-2 max-560:text-[24px]">
                  {title}
                </h3>
                <p className="max-w-[360px] text-[17px] text-mute max-560:text-[15px]">{body}</p>
              </article>
            ))}
          </div>

          <div className="turn-glow relative col-2 row-[1/3] min-h-0 max-960:col-1 max-960:row-2">
            {!ready && (
              <img
                src={media("turntable-poster.webp")}
                className="absolute inset-0 size-full object-contain"
                alt="Mirae viewed from the front left"
                loading="lazy"
                width="1080"
                height="900"
              />
            )}
            <canvas
              ref={canvasRef}
              className={cx("relative size-full", !ready && "invisible")}
              role="img"
              aria-hidden={!ready}
              aria-label="Mirae turning a full 360 degrees as you scroll"
            />
          </div>

          <div
            className="col-2 row-3 w-[min(420px,100%)] justify-self-end max-960:col-1 max-960:row-4 max-960:w-full"
            aria-hidden="true"
          >
            <div className="h-0.5 overflow-hidden rounded-[2px] bg-line">
              <span ref={fillRef} className="block h-full origin-left [transform:scaleX(0)] bg-ink" />
            </div>
            <ol className="mt-3 grid grid-cols-4 font-mono text-[11px] leading-none font-medium tracking-[0.14em] text-[#a39b91] uppercase [transition:color_0.3s]">
              {CHAPTERS.map(({ label }, i) => (
                <li key={label} className={cx(i <= chapter && "text-ink") || undefined}>
                  {label}
                </li>
              ))}
            </ol>
          </div>
          <p className="col-1 row-3 self-end font-mono text-[11px] leading-[1.5] font-medium text-mute max-960:hidden">
            Rendered in 3D from the exact printable model.
          </p>
        </div>
      </div>
    </section>
  );
}
