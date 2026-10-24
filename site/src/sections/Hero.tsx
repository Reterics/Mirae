import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { type RefObject, useRef } from "react";

import { ButtonLink } from "../components/Link";
import { media, reducedMotion } from "../lib";
import { LINKS } from "../site";
import { ctaButton, ctaRow, eyebrow, eyebrowDot } from "../ui";

const TITLE_LINES = ["A gatekeeper for your life.", "Present. Private. Yours."];

/** Full-bleed photo of the robot at home, with an intro animation and a slow drift on scroll. */
export function Hero({ sectionRef }: { sectionRef: RefObject<HTMLElement | null> }) {
  const imgRef = useRef<HTMLImageElement>(null);

  useGSAP(
    (_, contextSafe) => {
      const img = imgRef.current;
      if (!img || !contextSafe || reducedMotion) return;
      // contextSafe: the intro starts after the image loads, but must still be reverted on unmount.
      const intro = contextSafe(() => {
        gsap
          .timeline({ defaults: { ease: "expo.out" } })
          .from(img, { scale: 1.06, duration: 2.4 }, 0)
          .from("[data-intro-line]", { yPercent: 105, duration: 1.2, stagger: 0.1 }, 0.1)
          .from("[data-intro]", { y: 18, opacity: 0, duration: 1, stagger: 0.08 }, 0.25);
        gsap.to(img, {
          yPercent: 8,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top top", end: "bottom top", scrub: true },
        });
      });
      if (img.complete) intro();
      else img.addEventListener("load", intro, { once: true });
      return () => img.removeEventListener("load", intro);
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      className="hero-scrim relative isolate grid min-h-[min(100svh,980px)] items-end overflow-hidden text-white max-560:min-h-svh"
      id="top"
      aria-labelledby="hero-title"
    >
      <picture className="absolute inset-0 -z-1 size-full">
        <source media="(max-width: 760px)" srcSet={media("hero-portrait.webp")} width="1200" height="1500" />
        <img
          ref={imgRef}
          className="absolute inset-0 size-full object-cover object-[70%_60%] max-560:object-[50%_62%]"
          src={media("hero.webp")}
          width="2560"
          height="1280"
          alt="Mirae, a small warm-white and charcoal robot with two glowing eyes, on an oak floor in a sunlit living room"
        />
      </picture>
      <div className="hero-copy pt-[calc(var(--header-h)+48px)] pb-[clamp(48px,10vh,112px)] max-560:self-start max-560:pt-[calc(var(--header-h)+28px)]">
        <p className={`${eyebrow} text-[rgb(255_255_255/0.85)]`} data-intro>
          <span className={eyebrowDot} aria-hidden="true" />
          Open-source companion robot
        </p>
        <h1
          className="my-6 max-w-[22ch] text-[length:clamp(43px,5.4vw,86px)] leading-[0.98] tracking-[-0.05em] max-560:mt-[18px] max-560:mb-4 max-560:text-[39px]"
          id="hero-title"
        >
          {TITLE_LINES.map((line) => (
            <span key={line} className="block overflow-hidden pb-[0.06em] last:text-[0.96em]">
              <span className="inline-block text-balance" data-intro-line>
                {line}
              </span>
            </span>
          ))}
        </h1>
        <p
          className="max-w-[470px] text-[length:clamp(17px,1.35vw,19px)] text-[rgb(255_255_255/0.88)] max-560:text-[16px]"
          data-intro
        >
          A local-first companion that sees, listens and protects - while keeping what it learns close to you.
        </p>
        <div className={ctaRow} data-intro>
          <ButtonLink variant="light" className={ctaButton} href="#abilities">
            See what it does
          </ButtonLink>
          <ButtonLink variant="glass" className={ctaButton} href={LINKS.repo}>
            View on GitHub
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
