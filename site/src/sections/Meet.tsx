import { Title } from "../components/SectionHead";
import { cx, media } from "../lib";
import { lead, photo } from "../ui";

export function Meet() {
  return (
    <section
      className="wrap grid grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] items-center gap-[clamp(32px,6vw,96px)] py-[clamp(96px,14vh,160px)] max-960:grid-cols-1"
      aria-labelledby="meet-title"
    >
      <div className="grid gap-5" data-reveal>
        <Title id="meet-title" eyebrow="Meet Mirae" title="It lives on your floor," muted="not on your desk." />
        <p className={cx(lead, "max-w-[560px] text-mute")}>
          A two-wheeled companion that notices you, follows the conversation and keeps out of the way. It doesn't try to
          look human: no mouth, no ears, no cartoon face. Just a soft body and two points of light.
        </p>
      </div>
      <figure className="m-0" data-reveal>
        <img
          className={cx(photo, "bg-sunk")}
          src={media("people.webp")}
          width="2048"
          height="1147"
          loading="lazy"
          alt="A child sitting cross-legged on a living-room floor smiles at Mirae while a parent reads on the sofa behind"
        />
        <figcaption className="mt-3 font-mono text-[12px] leading-[1.5] font-medium text-mute">
          Illustration, AI-generated from a render of the model.
        </figcaption>
      </figure>
    </section>
  );
}
