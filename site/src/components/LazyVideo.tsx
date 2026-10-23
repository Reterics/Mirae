import { useEffect, useRef } from "react";

import { media, reducedMotion } from "../lib";

/**
 * A muted, looping background video that only downloads once it comes near the viewport and
 * only plays while visible. `name` picks media/<name>.webm|.mp4 and media/<name>-poster.jpg.
 */
export function LazyVideo({ name, className }: { name: string; className?: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    let loaded = false;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) {
          video.pause();
          return;
        }
        if (!loaded) {
          for (const source of video.querySelectorAll("source")) source.src = source.dataset.src ?? "";
          video.load();
          loaded = true;
        }
        if (!reducedMotion) video.play().catch(() => undefined);
      },
      { rootMargin: "300px 0px" },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  return (
    <video
      ref={ref}
      className={className}
      muted
      loop
      playsInline
      preload="none"
      poster={media(`${name}-poster.jpg`)}
      aria-hidden="true"
    >
      <source data-src={media(`${name}.webm`)} type="video/webm" />
      <source data-src={media(`${name}.mp4`)} type="video/mp4" />
    </video>
  );
}
