import { SectionHead } from "../components/SectionHead";
import { SPEC, XRAY_LABELS } from "../content";
import { cx, media } from "../lib";
import { photo } from "../ui";
import anchors from "../xray-anchors.json";

const ANCHORS: Partial<Record<string, readonly number[]>> = anchors;

/**
 * A label's dot sits on the projected 3D anchor (left/top from xray-anchors.json), and the text
 * runs out on a hairline: dot, line, text on the right; mirrored on the left.
 */
const LABEL = cx(
  "pointer-events-none absolute flex items-center gap-2.5 font-mono text-[12px] leading-none font-medium tracking-[0.06em] whitespace-nowrap text-ink",
  "before:size-[9px] before:rounded-[50%] before:bg-accent before:[box-shadow:0_0_0_3px_rgb(255_255_255/0.9)] before:content-['']",
  "after:order-1 after:h-px after:w-10 after:bg-ink after:opacity-35 after:content-['']",
);

export function Inside() {
  return (
    <section
      className="border-y border-y-line bg-surface py-[clamp(96px,14vh,160px)]"
      id="inside"
      aria-labelledby="inside-title"
    >
      <div className="wrap">
        <SectionHead id="inside-title" eyebrow="Inside" title="Off-the-shelf parts." muted="Nothing exotic." />
        <div
          className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] items-center gap-[clamp(28px,5vw,80px)] max-960:grid-cols-1"
          data-reveal
        >
          <figure className="relative m-0">
            <img
              className={cx(photo, "bg-bg")}
              src={media("xray.webp")}
              width="1800"
              height="1350"
              loading="lazy"
              alt="Cutaway of Mirae with the lid lifted off: a Raspberry Pi 5 in the upper tray, two 18650 cells below it, the speaker behind the side grille and the drive wheels in the base"
            />
            {/* too tight to point at parts on phones; the spec list beside it names them */}
            <ol className="max-560:hidden" aria-hidden="true">
              {XRAY_LABELS.map(({ anchor, side, text }) => {
                const [x, y] = ANCHORS[anchor] ?? [];
                if (x === undefined || y === undefined) return null;
                return (
                  <li
                    key={anchor}
                    className={cx(
                      LABEL,
                      side === "l"
                        ? "[transform:translate(calc(-100%+4.5px),-50%)] flex-row-reverse"
                        : "[transform:translate(-4.5px,-50%)]",
                    )}
                    style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
                  >
                    <span className="order-2">{text}</span>
                  </li>
                );
              })}
            </ol>
          </figure>
          <dl className="m-0 border-t border-t-line-strong">
            {SPEC.map(({ term, detail }) => (
              <div
                key={term}
                className="grid grid-cols-[120px_1fr] gap-5 border-b border-b-line py-[18px] max-560:grid-cols-1 max-560:gap-1"
              >
                <dt className="font-mono text-[12px] leading-[1.7] font-medium tracking-[0.14em] text-mute uppercase">
                  {term}
                </dt>
                <dd className="m-0">{detail}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
