/** Classes for a step's figure: the frame, the stage with its overlay and label, and the controls below. */
export const FIGURE = {
  /** Fills its panel on the one-screen layout; a 4:3 block in the page flow on narrow screens. */
  frame:
    "m-0 flex h-full flex-col rounded-card-lg bg-surface p-4 [box-shadow:0_0_0_1px_var(--color-line)] max-960:h-auto max-960:p-2",
  stage: "relative min-h-0 flex-1 max-960:aspect-[4/3] max-960:flex-none",
  /** The canvas, the poster and the SVG overlay all fill the stage. */
  layer: "absolute inset-0 size-full",
  arrow: "stroke-accent stroke-4 [stroke-dasharray:10_9] [stroke-linecap:round] [transition:opacity_0.3s]",
  arrowHead: "fill-accent",
  label:
    "pointer-events-none absolute rounded-[999px] bg-ink px-[11px] py-1.5 font-sans text-[13px] leading-none font-medium whitespace-nowrap text-bg [transform:translate(40px,-50%)]",
  controls: "flex items-center gap-4 px-1 pt-3 pb-0 max-560:gap-2.5 max-560:px-0",
  /** min-w-0: a range input's default width would push Reset view out of a phone-width frame. */
  scrub: "min-w-0 flex-1 accent-accent",
} as const;
