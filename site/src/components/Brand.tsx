import { Link as RouterLink } from "react-router";

import logo from "../../../assets/brand/mirae-logo-256.png";
import { useIsHome } from "../hooks/useIsHome";
import { cx } from "../lib";
import { SITE } from "../site";

const BRAND = "inline-flex items-center gap-[11px] justify-self-start";

/** Logo and name: back to the top on the landing page, back home everywhere else. `light` is for the hero photo. */
export function Brand({ light = false }: { light?: boolean }) {
  const content = (
    <>
      {/* -6px left: the logo PNG has a little transparent padding */}
      <img className="-my-1 -mr-1 -ml-1.5 size-10 object-contain" src={logo} alt="" width="40" height="40" />
      <span className={cx("text-[19px] font-semibold tracking-[-0.03em]", light && "text-white")}>{SITE.name}</span>
    </>
  );
  return useIsHome() ? (
    <a className={BRAND} href="#top" aria-label={`${SITE.name}, back to top`}>
      {content}
    </a>
  ) : (
    <RouterLink className={BRAND} to="/" aria-label={`${SITE.name}, home`}>
      {content}
    </RouterLink>
  );
}
