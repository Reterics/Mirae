import { SectionHead } from "../components/SectionHead";
import { SPEC } from "../content";
import { media } from "../lib";

export function Inside() {
  return (
    <section
      className="border-y border-y-line bg-surface py-[clamp(96px,14vh,160px)]"
      id="inside"
      aria-labelledby="inside-title"
    >
      <div className="wrap">
        <SectionHead
          id="inside-title"
          eyebrow="Inside"
          title="Off-the-shelf parts."
          muted="Nothing exotic."
          reveal={false}
        />
        <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] items-center gap-[clamp(28px,5vw,80px)] max-960:grid-cols-1">
          <figure className="relative m-0 aspect-[4/3] min-w-0">
            <img
              className="absolute inset-0 size-full rounded-card-lg object-cover"
              src={media("inside-exploded.png")}
              width="1498"
              height="1124"
              loading="lazy"
              alt="Exploded view of Mirae with labels and leader lines identifying the Raspberry Pi 5, AI HAT+ 2, speaker and audio, power electronics, four 18650 cells, N20 drive, camera and ToF sensor, and ball caster"
            />
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
