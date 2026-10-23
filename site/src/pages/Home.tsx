import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef } from "react";

import { SkipLink } from "../components/SkipLink";
import { useSmoothScroll } from "../hooks/useSmoothScroll";
import { reducedMotion } from "../lib";
import { Abilities } from "../sections/Abilities";
import { Build } from "../sections/Build";
import { CallToAction } from "../sections/CallToAction";
import { Design } from "../sections/Design";
import { Facts } from "../sections/Facts";
import { Footer } from "../sections/Footer";
import { Header } from "../sections/Header";
import { Hero } from "../sections/Hero";
import { HowItWorks } from "../sections/HowItWorks";
import { Inside } from "../sections/Inside";
import { Meet } from "../sections/Meet";
import { QuickStart } from "../sections/QuickStart";
import { Roadmap } from "../sections/Roadmap";
import { SITE } from "../site";

export function Home() {
  const mainRef = useRef<HTMLElement>(null);
  const heroRef = useRef<HTMLElement>(null);

  useSmoothScroll();

  // Fade and lift every [data-reveal] element as it enters the viewport.
  useGSAP(
    () => {
      if (reducedMotion) return;
      gsap.set("[data-reveal]", { opacity: 0, y: 28 });
      ScrollTrigger.batch("[data-reveal]", {
        start: "top 88%",
        once: true,
        onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: 1, ease: "expo.out", stagger: 0.08 }),
      });
    },
    { scope: mainRef },
  );

  // Lazy images change the layout, so re-measure every trigger once everything has loaded.
  useEffect(() => {
    const refresh = (): void => ScrollTrigger.refresh();
    window.addEventListener("load", refresh);
    return () => window.removeEventListener("load", refresh);
  }, []);

  return (
    <>
      <title>{SITE.title}</title>
      <SkipLink />
      <Header heroRef={heroRef} />
      <main ref={mainRef} id="main">
        <Hero sectionRef={heroRef} />
        <Facts />
        <Meet />
        <Abilities />
        <Inside />
        <Design />
        <Build />
        <HowItWorks />
        <Roadmap />
        <QuickStart />
        <CallToAction />
      </main>
      <Footer />
    </>
  );
}
