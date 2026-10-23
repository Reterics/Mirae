import { Fragment } from "react";

import type { TermLine, Token } from "../content";
import { cx } from "../lib";

const TOKEN_CLASS: Record<Token, string | undefined> = {
  comment: "text-[#8f877d]",
  key: "text-[#e8d5c0]",
  value: "text-[#a7dcb4]",
  accent: "text-[#f0b27a]",
  error: undefined,
};

/** A terminal window showing pre-highlighted lines. */
export function Terminal({
  title,
  lines,
  large = false,
}: {
  title: string;
  lines: readonly TermLine[];
  large?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-card bg-[#1c1a18] text-[#ede8e1]" data-reveal>
      <div className="flex items-center gap-[7px] border-b border-b-[rgb(255_255_255/0.08)] px-[18px] py-3.5">
        <i className="size-2.5 rounded-[50%] bg-[#3a3632]" />
        <i className="size-2.5 rounded-[50%] bg-[#3a3632]" />
        <i className="size-2.5 rounded-[50%] bg-[#3a3632]" />
        <span className="ml-2 font-mono text-[12px] leading-none font-medium text-[#8f877d]">{title}</span>
      </div>
      <pre
        className={cx(
          "m-0 p-6 font-mono leading-[1.75] font-medium [word-break:break-word] whitespace-pre-wrap",
          large ? "min-h-[290px] text-[13px]" : "min-h-[110px] text-[14px]",
        )}
      >
        <code>
          {lines.map((line, i) => (
            <Fragment key={i}>
              {i > 0 && "\n"}
              {line.map((seg, j) =>
                typeof seg === "string" ? (
                  seg
                ) : (
                  <span key={j} className={TOKEN_CLASS[seg[0]]}>
                    {seg[1]}
                  </span>
                ),
              )}
            </Fragment>
          ))}
        </code>
      </pre>
    </div>
  );
}
