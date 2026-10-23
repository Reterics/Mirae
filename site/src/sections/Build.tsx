import { Link as RouterLink } from "react-router";

import { ButtonLink } from "../components/Link";
import { LazyVideo } from "../components/LazyVideo";
import { SectionHead } from "../components/SectionHead";
import { type Filament, PARTS } from "../content";
import { cx } from "../lib";
import { LINKS } from "../site";
import { buttonClass, ctaButton, lead } from "../ui";

const SWATCH: Record<Filament, string> = { white: "bg-[#f1ede6]", charcoal: "bg-[#34302d]", black: "bg-[#111]" };

export function Build() {
  return (
    <section
      className="wrap grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-[clamp(32px,6vw,96px)] border-t border-t-line py-[clamp(96px,14vh,160px)] max-960:grid-cols-1"
      id="build"
      aria-labelledby="build-title"
    >
      <figure
        className="m-0 aspect-[4/5] overflow-hidden rounded-card-lg bg-[#2a2623] max-960:aspect-[16/10]"
        data-reveal
      >
        <LazyVideo name="print" className="size-full object-cover object-[34%_50%]" />
      </figure>
      <div>
        <SectionHead
          className="mb-[22px] grid gap-[18px]"
          id="build-title"
          eyebrow="Build it yourself"
          title="Print it tonight."
          muted="Wire it this weekend."
        />
        <p className={cx(lead, "max-w-[560px] text-mute")} data-reveal>
          Get the ready-to-print STL files and follow the step-by-step assembly guide. Each part fits a 220 × 220 mm bed
          and prints in PLA or PETG. Check the part dimensions and hardware clearances before assembly.
        </p>
        <table className="mt-7 w-full border-collapse text-[15px] max-560:text-[14px]" data-reveal>
          <caption className="sr-only">Printed parts, print size in millimetres and colour</caption>
          <thead>
            <tr>
              {["Part", "Size (mm)", "Colour"].map((heading) => (
                <th
                  key={heading}
                  scope="col"
                  className="border-b border-b-line-strong px-0 pt-0 pb-3 text-left font-mono text-[11px] leading-none font-medium tracking-[0.14em] text-mute uppercase"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PARTS.map(({ name, size, colour }) => (
              <tr key={name} className="[&>td]:border-b [&>td]:border-b-line [&>td]:px-0 [&>td]:py-3">
                <td className="font-mono text-[14px] leading-none font-medium">{name}</td>
                <td className="text-ink-2 tabular-nums">{size}</td>
                <td className="text-mute">
                  <i
                    className={cx(
                      "mr-2 inline-block size-[11px] rounded-[50%] align-[-1px] [box-shadow:inset_0_0_0_1px_rgb(0_0_0/0.14)]",
                      SWATCH[colour],
                    )}
                  />
                  {colour}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-[30px] flex flex-wrap gap-3" data-reveal>
          <RouterLink className={cx(buttonClass("dark"), ctaButton)} to="/assembly">
            Open the assembly guide
          </RouterLink>
          <ButtonLink variant="line" className={ctaButton} href={LINKS.stl}>
            STL files
          </ButtonLink>
          <ButtonLink variant="line" className={ctaButton} href={LINKS.partsList}>
            Parts list
          </ButtonLink>
        </div>
      </div>
    </section>
  );
}
