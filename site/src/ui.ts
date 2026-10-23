/** Tailwind class lists for the small type and decoration styles that several components share. */

import { cx } from "./lib";

/** Mono uppercase label; callers add tracking and colour. */
export const label = "font-mono text-[12px] leading-none font-medium uppercase";

export const eyebrow = `${label} inline-flex items-center gap-2.5 tracking-[0.18em]`;
export const eyebrowDot = "size-[7px] rounded-[50%] bg-accent [box-shadow:0_0_0_4px_rgb(232_150_74/0.16)]";

/** Numbered kicker above a heading ("01 · Base"). */
export const kicker = `${label} tracking-[0.14em] text-accent-ink`;

export const h2 = "text-[length:clamp(36px,4.6vw,68px)]";
export const h1 = "text-[length:clamp(44px,6vw,88px)] tracking-[-0.045em]";

/** Lead paragraph size; callers add width and colour. */
export const lead = "text-[length:clamp(17px,1.3vw,19px)]";

export const textLink =
  "border-b border-b-line-strong font-medium text-ink [transition:border-color_0.2s] hover:border-ink";

/** Full-width rounded image; callers add the tint shown while it loads. */
export const photo = "h-auto w-full rounded-card-lg";

/** Row of call-to-action buttons; on phones each button grows to share the row. */
export const ctaRow = "mt-[34px] flex flex-wrap gap-3 max-560:mt-[26px]";
export const ctaButton = "max-560:flex-auto";

const VARIANTS = {
  dark: "bg-ink text-bg hover:bg-[#34302c]",
  line: "border border-line bg-surface text-ink hover:border-line-strong",
  light: "bg-[#fbf9f6] text-ink hover:bg-white",
  glass:
    "border border-[rgb(255_255_255/0.35)] bg-[rgb(255_255_255/0.12)] text-white [backdrop-filter:blur(10px)] hover:bg-[rgb(255_255_255/0.2)]",
  /** The header's line button while it sits over the hero photo. */
  over: "border border-[rgb(255_255_255/0.35)] bg-[rgb(255_255_255/0.12)] text-white",
} as const;

export type ButtonVariant = keyof typeof VARIANTS;

/** Classes for a pill button, on a link or a `<button>`. */
export const buttonClass = (variant: ButtonVariant, small = false): string =>
  cx(
    "inline-flex items-center justify-center gap-[9px] rounded-[999px] font-sans leading-none font-medium tracking-[-0.01em] whitespace-nowrap",
    "[transition:background-color_0.25s,border-color_0.25s,color_0.25s,transform_0.4s_var(--ease)] active:[transform:scale(0.97)]",
    "[&_svg]:size-4 [&_svg]:flex-none",
    small ? "h-[38px] px-4 py-0 text-[14px]" : "h-12 px-[22px] py-0 text-[15px]",
    VARIANTS[variant],
  );
