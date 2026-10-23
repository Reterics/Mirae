import type { ReactNode } from "react";

import { cx } from "../lib";
import { eyebrow, h2 } from "../ui";

interface TitleProps {
  id: string;
  eyebrow: string;
  title: string;
  muted: string;
  /** Extra classes for the eyebrow and the heading. */
  eyebrowClassName?: string;
  titleClassName?: string;
}

/** Eyebrow and a two-line heading whose second line is muted. */
export function Title({ id, eyebrow: text, title, muted, eyebrowClassName, titleClassName }: TitleProps) {
  return (
    <>
      <p className={cx(eyebrow, "text-mute", eyebrowClassName)}>{text}</p>
      <h2 className={cx(h2, titleClassName)} id={id}>
        {title}
        <br />
        <span className="text-mute">{muted}</span>
      </h2>
    </>
  );
}

export const SEC_HEAD = "grid gap-[18px] mb-[clamp(36px,5vw,56px)]";

/** A section's `<header>`: the title plus optional lead or note. */
export function SectionHead({
  className = SEC_HEAD,
  centered = false,
  reveal = true,
  children,
  ...title
}: TitleProps & { className?: string; centered?: boolean; reveal?: boolean; children?: ReactNode }) {
  return (
    <header className={cx(className, centered && "justify-items-center text-center")} data-reveal={reveal || undefined}>
      <Title {...title} />
      {children}
    </header>
  );
}
