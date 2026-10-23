import { FACTS } from "../content";
import { cx } from "../lib";

export function Facts() {
  return (
    <div className="wrap">
      <ul
        className="grid grid-cols-4 border-b border-b-line pt-7 pb-8 max-960:grid-cols-2 max-960:gap-x-0 max-960:gap-y-[18px]"
        aria-label="Key facts"
      >
        {FACTS.map(({ value, detail }, i) => (
          <li
            key={value}
            className={cx(
              "grid gap-0.5 pr-5",
              i > 0 && "border-l border-l-line pl-6",
              // two per row below 960px: the third starts the second row
              i === 2 && "max-960:pl-0 max-960:[border-left:0]",
            )}
          >
            <b className="text-[20px] font-medium tracking-[-0.02em] max-560:text-[17px]">{value}</b>
            <span className="text-[14px] text-mute max-560:text-[13px]">{detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
