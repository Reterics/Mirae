import { SectionHead } from "../components/SectionHead";
import { ROADMAP } from "../content";
import { cx, media } from "../lib";
import { eyebrow, eyebrowDot } from "../ui";

export function Roadmap() {
  return (
    <section
      className="wrap border-t border-t-line py-[clamp(80px,12vh,140px)]"
      id="roadmap"
      aria-labelledby="road-title"
    >
      <SectionHead id="road-title" eyebrow="Roadmap" title="Built in the open," muted="one version at a time.">
        <p className="inline-flex items-center gap-2.5 justify-self-start rounded-[999px] border border-line bg-surface px-4 py-2.5 text-[14px] text-ink-2">
          <span className={eyebrowDot} aria-hidden="true" />
          Early prototype: the software runs in simulation; the Pi drivers are written but not yet tested on the robot.
        </p>
      </SectionHead>
      {/* a timeline: one rule across the top with a dot per version; it wraps into rows below 1080px */}
      <ol className="grid grid-cols-7 border-t border-t-line-strong max-1080:grid-cols-4 max-1080:gap-y-9 max-1080:[border-top:0] max-560:grid-cols-2">
        {ROADMAP.map(({ version, title, body, current }) => (
          <li
            key={version}
            className={cx(
              "relative pt-[26px] pr-[18px] max-1080:border-t max-1080:border-t-line-strong",
              "before:absolute before:-top-[5px] before:left-0 before:size-[9px] before:rounded-[50%] before:border-[1.5px] before:content-['']",
              current
                ? "before:border-accent before:bg-accent before:[box-shadow:0_0_0_5px_rgb(232_150_74/0.18)]"
                : "before:border-line-strong before:bg-bg",
            )}
            data-reveal
          >
            <b className="font-mono text-[12px] leading-none font-medium text-mute">{version}</b>
            <h3 className="mt-2.5 mb-1.5 text-[20px] tracking-[-0.02em]">{title}</h3>
            <p className="text-[14px] text-mute">{body}</p>
            {current && (
              <span className="mt-3 inline-block rounded-[999px] bg-[rgb(232_150_74/0.14)] px-2.5 py-1.5 font-mono text-[11px] leading-none font-medium text-accent-ink">
                In progress
              </span>
            )}
          </li>
        ))}
      </ol>

      {/* Beyond the roadmap: concept art, kept apart from the timeline so it never reads as a plan. On wide
          screens the text sits in the empty top-left of the cut-out; on narrow ones it stacks and the art
          scrolls sideways at a readable size. */}
      <figure
        className="relative m-0 mt-[clamp(72px,10vw,128px)] border-t border-t-line pt-[clamp(48px,6vw,72px)]"
        aria-labelledby="bodies-title"
        data-reveal
      >
        <div className="absolute top-[clamp(48px,6vw,72px)] left-0 z-1 max-w-[440px] max-960:static max-960:mb-8">
          <p className={cx(eyebrow, "text-mute")}>Beyond v1.0</p>
          <h3
            className="mt-[18px] text-[length:clamp(30px,3.2vw,46px)] leading-[1.05] tracking-[-0.035em]"
            id="bodies-title"
          >
            One head.
            <br />
            <span className="text-mute">Any body.</span>
          </h3>
          <p className="mt-4 max-w-[360px] text-[17px] text-mute">
            The software doesn&rsquo;t define its form. It can become anything.
          </p>
        </div>
        <div
          className="[scrollbar-width:thin] overflow-x-auto max-960:-mx-(--gutter) max-960:px-(--gutter)"
          role="region"
          aria-label="Concept art, scrolls sideways on small screens"
          tabIndex={0}
        >
          <img
            className="block h-auto w-full max-960:w-[760px] max-960:max-w-none"
            src={media("bodies.webp")}
            width="1765"
            height="717"
            loading="lazy"
            alt="Concept art: the same Mirae head on four bodies: today's two-wheeled base, a floor-cleaning robot, a four-wheeled outdoor rover and a humanoid"
          />
        </div>
        <figcaption className="mt-3 font-mono text-[12px] leading-[1.5] font-medium text-mute">
          Concept art, AI-generated. Ideas, not plans: none of these is on the roadmap.
        </figcaption>
      </figure>
    </section>
  );
}
