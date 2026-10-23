import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useEffect, useState } from "react";
import { useLocation } from "react-router";

import { reducedMotion } from "../lib";

/**
 * Lenis smooth scrolling driven by GSAP's ticker (skipped for reduced motion), plus smooth
 * in-page navigation for every `href="#…"` section link, which also moves focus to the target.
 * Route links (`href="#/…"`) are left to the router.
 */
export function useSmoothScroll(): void {
  // Only the section the page was opened with (#/#abilities) counts; in-page clicks don't route.
  const [initialHash] = useState(useLocation().hash);
  useEffect(() => {
    const lenis = reducedMotion ? null : new Lenis({ lerp: 0.1 });
    const tick = (time: number): void => lenis?.raf(time * 1000);
    if (lenis) {
      lenis.on("scroll", () => {
        ScrollTrigger.update();
      });
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
    }

    const onClick = (e: MouseEvent): void => {
      if (e.defaultPrevented) return;
      const link =
        e.target instanceof Element ? e.target.closest<HTMLAnchorElement>('a[href^="#"]:not([href^="#/"])') : null;
      const id = link?.getAttribute("href");
      if (!id) return;
      const target = id === "#top" ? 0 : document.querySelector<HTMLElement>(id);
      if (target === null) return;
      e.preventDefault();
      if (lenis) lenis.scrollTo(target, { offset: 0, duration: 1.4 });
      else window.scrollTo({ top: target === 0 ? 0 : target.offsetTop, behavior: reducedMotion ? "auto" : "smooth" });
      if (target !== 0) target.focus({ preventScroll: true });
    };
    document.addEventListener("click", onClick);

    // Arriving from another page with a section in the URL: go straight there.
    const initial = initialHash ? document.getElementById(initialHash.slice(1)) : null;
    const frame = initial
      ? requestAnimationFrame(() => {
          if (lenis) lenis.scrollTo(initial, { immediate: true });
          else initial.scrollIntoView();
        })
      : 0;

    return () => {
      document.removeEventListener("click", onClick);
      cancelAnimationFrame(frame);
      gsap.ticker.remove(tick);
      gsap.ticker.lagSmoothing(500, 33);
      lenis?.destroy();
    };
  }, [initialHash]);
}
