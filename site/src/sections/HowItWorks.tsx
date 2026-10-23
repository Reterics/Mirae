import { SectionHead } from "../components/SectionHead";
import { Terminal } from "../components/Terminal";
import { INTENT_EXAMPLE, PIPELINE, type PipelineStep, VOCABULARY } from "../content";
import { cx } from "../lib";
import { lead } from "../ui";

/** The numbered circle on each pipeline step: amber for the AI, solid ink for the safety layer. */
const STEP_NUMBER: Record<NonNullable<PipelineStep["variant"]> | "default", string> = {
  default: "before:border-line-strong before:bg-surface before:text-ink-2",
  ai: "before:border-accent before:bg-surface before:text-accent-ink",
  safe: "before:border-ink before:bg-ink before:text-bg",
};

export function HowItWorks() {
  return (
    <section
      className="border-y border-y-line bg-surface py-[clamp(96px,14vh,160px)]"
      id="how"
      aria-labelledby="how-title"
    >
      <div className="wrap">
        <SectionHead centered id="how-title" eyebrow="How it works" title="The AI suggests." muted="Safety decides.">
          <p className={cx(lead, "max-w-[620px] text-mute")}>
            The language model never drives the motors. It produces high-level intents, and a deterministic behavior
            engine turns them into safe movements.
          </p>
        </SectionHead>

        <ol
          className={cx(
            "relative mb-[clamp(40px,6vw,72px)] grid grid-cols-6 gap-3 [counter-reset:step] max-960:grid-cols-3 max-960:gap-y-7",
            // the line joining the steps, hidden once they wrap
            "before:absolute before:top-[23px] before:right-[8%] before:left-[8%] before:h-px before:bg-line-strong before:content-[''] max-960:before:hidden",
          )}
          data-reveal
          aria-label="Data flow"
        >
          {PIPELINE.map(({ name, detail, variant }) => (
            <li
              key={name}
              className={cx(
                "relative grid justify-items-center gap-1 text-center [counter-increment:step]",
                "before:relative before:z-1 before:mb-3.5 before:grid before:size-[46px] before:place-items-center before:rounded-[50%] before:border",
                "before:font-mono before:text-[12px] before:leading-none before:font-medium before:content-[counter(step,decimal-leading-zero)]",
                STEP_NUMBER[variant ?? "default"],
              )}
            >
              <b className="text-[16px] font-medium">{name}</b>
              <span className="font-mono text-[12px] leading-[1.4] font-medium text-mute">{detail}</span>
            </li>
          ))}
        </ol>

        <div className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-4 max-960:grid-cols-1">
          <Terminal title="intents from the AI layer" lines={INTENT_EXAMPLE} />
          <div className="grid content-start gap-2.5 rounded-card border border-line bg-bg p-7" data-reveal>
            <h3 className="text-[24px] tracking-[-0.025em]">The complete vocabulary.</h3>
            <p className="text-mute">Anything else is rejected.</p>
            <ul className="mt-3 mb-2 flex flex-wrap gap-2">
              {VOCABULARY.map((word) => (
                <li
                  key={word}
                  className="rounded-[9px] border border-line bg-surface px-3 py-[9px] font-mono text-[13px] leading-none font-medium"
                >
                  {word}
                </li>
              ))}
            </ul>
            <p className="text-[14px] text-mute">
              Speeds and durations are bounded in the schema (at most 5 s per move), then bounded again by the safety
              governor.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
