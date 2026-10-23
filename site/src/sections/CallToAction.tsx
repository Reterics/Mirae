import { Link as RouterLink } from "react-router";

import { ButtonLink } from "../components/Link";
import { LazyVideo } from "../components/LazyVideo";
import { cx } from "../lib";
import { LINKS } from "../site";
import { buttonClass, ctaButton, ctaRow, h1, lead } from "../ui";

export function CallToAction() {
  return (
    <section
      className="cta-wash relative isolate grid min-h-[78svh] place-items-center overflow-hidden text-center"
      aria-labelledby="cta-title"
    >
      <LazyVideo name="floor" className="absolute inset-0 -z-2 size-full object-cover" />
      <div className="wrap grid justify-items-center gap-[22px]" data-reveal>
        <h2 className={h1} id="cta-title">
          Bring Mirae home.
        </h2>
        <p className={cx(lead, "max-w-[560px] text-ink-2")}>
          Open hardware, open software, and a body you can print yourself.
        </p>
        <div className={ctaRow}>
          <ButtonLink variant="dark" className={ctaButton} href={LINKS.repo}>
            Star on GitHub
          </ButtonLink>
          <RouterLink className={cx(buttonClass("line"), ctaButton)} to="/assembly">
            Assembly guide
          </RouterLink>
        </div>
      </div>
    </section>
  );
}
