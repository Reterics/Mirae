import { useRef } from "react";

import { Link } from "../components/Link";
import { cx } from "../lib";
import { LINKS, REPO } from "../site";
import { buttonClass, textLink } from "../ui";
import { SHOPPING_GROUPS, SHOPPING_TOOLS } from "./shopping";

export function ShoppingCart({ onOpen }: { onOpen: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);

  return (
    <>
      <button
        className={cx(buttonClass("line", true), "w-full cursor-pointer")}
        type="button"
        aria-haspopup="dialog"
        aria-controls="assembly-shopping-cart"
        onClick={() => {
          onOpen();
          dialog.current?.showModal();
        }}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M3 3h2l3 12h11l2-8H6" />
          <circle cx="9" cy="20" r="1" />
          <circle cx="18" cy="20" r="1" />
        </svg>
        Shopping cart
      </button>
      <dialog
        ref={dialog}
        id="assembly-shopping-cart"
        aria-labelledby="shopping-title"
        aria-describedby="shopping-description"
        className="fixed inset-0 m-auto max-h-[90dvh] w-[min(1120px,calc(100%_-_24px))] overflow-hidden rounded-xl border border-line-strong bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/40 open:flex open:flex-col"
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 id="shopping-title" className="text-[18px] tracking-[-0.02em]">
              Assembly shopping list
            </h2>
            <span className="font-mono text-[11px] text-mute">
              {SHOPPING_GROUPS.reduce((count, group) => count + group.parts.length, 0)} items · 1 robot
            </span>
          </div>
          <button
            className={cx(buttonClass("line", true), "cursor-pointer")}
            type="button"
            onClick={() => dialog.current?.close()}
          >
            Close
          </button>
        </div>
        <div className="shrink-0 border-b border-line bg-bg/50 px-4 py-2.5">
          <p id="shopping-description" className="text-[12px] leading-relaxed text-ink-2">
            Quantities for one build. Unspecified parts link to sizing requirements. Supplier links open in a new tab.
          </p>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
            <Link className={textLink} href={LINKS.partsList} target="_blank">
              Hardware guide ↗
            </Link>
            <Link className={textLink} href={`${REPO}/raw/refs/heads/main/docs/hestore_20261022.xml`} target="_blank">
              HESTORE cart XML ↗
            </Link>
            <Link className={textLink} href={LINKS.cad} target="_blank">
              Print settings ↗
            </Link>
          </div>
        </div>
        <div
          className="min-h-0 [scrollbar-width:thin] overflow-auto overscroll-contain"
          role="region"
          aria-label="Assembly parts table"
          tabIndex={0}
        >
          <table className="w-full min-w-[760px] table-fixed border-collapse text-left text-[12px] leading-[1.4]">
            <caption className="sr-only">
              Parts, specifications, quantities and supplier links for one Mirae robot
            </caption>
            <colgroup>
              <col className="w-[27%]" />
              <col className="w-[43%]" />
              <col className="w-[7%]" />
              <col className="w-[23%]" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-sunk text-[11px] text-ink-2 [box-shadow:0_1px_0_var(--color-line-strong)]">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">
                  Part
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Specification / notes
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Qty
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Supplier / file
                </th>
              </tr>
            </thead>
            {SHOPPING_GROUPS.map(({ title, parts }) => (
              <tbody key={title}>
                <tr>
                  <th
                    scope="rowgroup"
                    colSpan={4}
                    className="border-y border-line bg-bg px-4 py-2 text-[11px] font-medium text-ink-2"
                  >
                    {title}
                    <span className="ml-2 font-mono text-[10px] font-normal text-mute">{parts.length} items</span>
                  </th>
                </tr>
                {parts.map(({ name, qty, description, href, source }) => (
                  <tr key={name} className="border-b border-line align-top transition-colors hover:bg-bg/70">
                    <th scope="row" className="px-4 py-2 font-medium [overflow-wrap:anywhere]">
                      {name}
                    </th>
                    <td className="px-3 py-2 text-ink-2">{description}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{qty}</td>
                    <td className="px-4 py-2">
                      <Link
                        className={cx(textLink, "inline-block [overflow-wrap:anywhere]")}
                        href={href}
                        target="_blank"
                        aria-label={`${name}: ${source} (opens in a new tab)`}
                      >
                        {source} ↗
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
        <details className="shrink-0 border-t border-line bg-bg/50 px-4 py-2.5 text-[12px]">
          <summary className="cursor-pointer font-medium">
            Tools and consumables <span className="ml-1 font-normal text-mute">({SHOPPING_TOOLS.length})</span>
          </summary>
          <ul className="mt-2 grid list-disc grid-cols-2 gap-x-6 gap-y-1 pl-4 text-ink-2 max-560:grid-cols-1">
            {SHOPPING_TOOLS.map((tool) => (
              <li key={tool}>{tool}</li>
            ))}
          </ul>
          <Link className={cx(textLink, "mt-2 inline-block")} href={LINKS.cad} target="_blank">
            Assembly and tool guidance ↗
          </Link>
        </details>
      </dialog>
    </>
  );
}
