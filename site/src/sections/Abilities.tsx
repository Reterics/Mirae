import { Link } from "../components/Link";
import { SEC_HEAD, SectionHead } from "../components/SectionHead";
import { PRINCIPLES, SCENES, type Scene, type Swatch } from "../content";
import { cx, media } from "../lib";
import { kicker, photo, textLink } from "../ui";

/** Image column first (wider), image column second (`flip`), or two equal columns (`map`). */
const COLUMNS: Record<NonNullable<Scene["variant"]> | "default", string> = {
  default: "grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]",
  flip: "grid-cols-[minmax(0,1fr)_minmax(0,1.55fr)]",
  map: "grid-cols-[minmax(0,1fr)_minmax(0,1fr)]",
};

/** Legend keys, matching how each thing is drawn in the scene image. */
const SWATCH: Record<Swatch, string> = {
  cam: "h-3 w-[22px] rounded-[3px] bg-[linear-gradient(90deg,rgb(232_150_74/0.75),rgb(232_150_74/0.15))]",
  tof: "h-3 w-[22px] rounded-[3px] bg-[linear-gradient(90deg,rgb(160_190_225/0.9),rgb(160_190_225/0.2))]",
  route: "h-[3px] w-[22px] rounded-[3px] bg-accent",
  stop: "size-[14px] rounded-[50%] bg-[rgb(240_120_80/0.55)]",
  dot: "mr-2 ml-[7px] size-[7px] rounded-[50%] bg-ink-2",
};

function SceneCard({ num, title, body, legend, image, variant }: Scene) {
  return (
    <article
      className={cx(
        "wrap grid items-center gap-[clamp(28px,5vw,80px)] py-[clamp(28px,4vw,52px)] max-960:grid-cols-1",
        COLUMNS[variant ?? "default"],
      )}
      data-reveal
    >
      <figure className={cx("m-0", variant === "flip" && "order-2 max-960:order-0")}>
        <img
          className={cx(photo, "bg-sunk")}
          src={media(image.file)}
          width={image.width}
          height={image.height}
          loading="lazy"
          alt={image.alt}
        />
      </figure>
      <div>
        <p className={kicker}>{num}</p>
        <h3 className="mt-3.5 mb-4 text-[length:clamp(30px,3vw,46px)]">{title}</h3>
        <p className="max-w-[440px] text-[18px] text-mute">{body}</p>
        <ul className="mt-[26px] grid max-w-[440px] gap-2.5 border-t border-t-line pt-5 text-[15px]">
          {legend.map(({ swatch, text }) => (
            <li key={text} className="flex items-center gap-3">
              <i className={cx("flex-none", SWATCH[swatch])} />
              {text}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

export function Abilities() {
  return (
    <section
      className="border-t border-t-line pt-[clamp(40px,6vh,72px)] pb-[clamp(96px,14vh,160px)]"
      id="abilities"
      aria-labelledby="abil-title"
    >
      <SectionHead
        className={cx(SEC_HEAD, "wrap pt-[clamp(56px,8vh,96px)]")}
        id="abil-title"
        eyebrow="Abilities"
        title="Small enough to ignore."
        muted="Smart enough not to."
      >
        <p className="max-w-[560px] text-[15px] text-mute">
          These are the capabilities the software and hardware are built for. They arrive milestone by milestone; see
          the{" "}
          <Link className={textLink} href="#roadmap">
            roadmap
          </Link>
          .
        </p>
      </SectionHead>

      {SCENES.map((scene) => (
        <SceneCard key={scene.num} {...scene} />
      ))}

      <ul
        className="wrap mt-[clamp(40px,6vw,72px)] grid grid-cols-3 gap-[clamp(24px,4vw,56px)] border-t border-t-line-strong pt-[clamp(32px,4vw,48px)] max-960:grid-cols-1"
        data-reveal
      >
        {PRINCIPLES.map(({ title, body }) => (
          <li key={title}>
            <h3 className="mb-2.5 text-[22px] tracking-[-0.02em]">{title}</h3>
            <p className="text-mute">{body}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
