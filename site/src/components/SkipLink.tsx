import type { MouseEvent } from "react";

/**
 * "Skip to content". Routes live in the URL hash, so a plain `href="#main"` would navigate to a
 * route called "main"; this moves focus and scroll to <main> instead.
 */
export function SkipLink() {
  const skip = (e: MouseEvent<HTMLAnchorElement>): void => {
    e.preventDefault();
    const main = document.getElementById("main");
    main?.scrollIntoView();
    main?.focus({ preventScroll: true });
  };
  return (
    <a
      className="fixed top-2.5 left-2.5 z-100 [transform:translateY(-160%)] rounded-[999px] bg-ink px-4 py-2.5 text-bg [transition:transform_0.3s_var(--ease)] focus:[transform:none]"
      href="#main"
      onClick={skip}
    >
      Skip to content
    </a>
  );
}
