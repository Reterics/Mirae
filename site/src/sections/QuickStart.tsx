import { Link } from "../components/Link";
import { Title } from "../components/SectionHead";
import { Terminal } from "../components/Terminal";
import { QUICK_START } from "../content";
import { cx } from "../lib";
import { LINKS } from "../site";
import { lead, textLink } from "../ui";

export function QuickStart() {
  return (
    <section
      className="wrap grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-center gap-[clamp(32px,6vw,96px)] border-t border-t-line py-[clamp(80px,12vh,140px)] max-960:grid-cols-1"
      aria-labelledby="quick-title"
    >
      <div className="grid justify-items-start gap-[18px]" data-reveal>
        <Title id="quick-title" eyebrow="No robot needed" title="Start hacking in" muted="three commands." />
        <p className={cx(lead, "max-w-[560px] text-mute")}>
          The whole stack runs against simulated hardware on Windows, macOS and Linux. You need Python 3.11+ and uv.
        </p>
        <Link className={textLink} href={LINKS.software}>
          Software documentation →
        </Link>
      </div>
      <Terminal large title="~/Mirae" lines={QUICK_START} />
    </section>
  );
}
