import { type RefObject, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useLocation } from "react-router";

import { Brand } from "../components/Brand";
import { GitHubIcon } from "../components/GitHubIcon";
import { ButtonLink } from "../components/Link";
import { NAV } from "../content";
import { cx } from "../lib";
import { LINKS } from "../site";

/**
 * Sticky header with page navigation and a mobile menu. Over a hero photo it starts transparent.
 */
export function Header({ heroRef }: { heroRef?: RefObject<HTMLElement | null> }) {
  const ref = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [overPhoto, setOverPhoto] = useState(heroRef !== undefined);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const update = (): void => {
      const y = window.scrollY;
      const over = !menuOpen && y < (heroRef?.current?.offsetHeight ?? 0) - (ref.current?.offsetHeight ?? 0);
      setOverPhoto(over);
      setScrolled(!over && y > 8);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [menuOpen, heroRef]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const closeMenu = (): void => setMenuOpen(false);
  const link = navLink(overPhoto);

  return (
    <header
      ref={ref}
      className={cx(
        "fixed inset-x-0 top-0 z-50 h-(--header-h) border-b",
        "[transition:border-color_0.3s,background-color_0.35s,backdrop-filter_0.35s]",
        overPhoto
          ? "border-b-transparent bg-transparent [backdrop-filter:none]"
          : "bg-[rgb(246_243_238/0.94)] [backdrop-filter:saturate(1.4)_blur(14px)]",
        !overPhoto && (scrolled ? "border-b-line" : "border-b-transparent"),
      )}
    >
      <div className="wrap grid h-full grid-cols-[1fr_auto_1fr] items-center gap-6 max-960:grid-cols-[1fr_auto]">
        <Brand light={overPhoto} />
        <nav
          className={cx(
            "flex gap-1",
            // phones and tablets: a panel that drops down under the bar
            "max-960:fixed max-960:inset-x-0 max-960:top-(--header-h) max-960:bottom-auto max-960:flex-col max-960:gap-0",
            "max-960:border-b max-960:border-b-line max-960:bg-bg max-960:px-(--gutter) max-960:pt-2 max-960:pb-5",
            menuOpen
              ? "max-960:visible max-960:[transform:none] max-960:opacity-100 max-960:[transition:opacity_0.25s,transform_0.35s_var(--ease)]"
              : "max-960:invisible max-960:[transform:translateY(-8px)] max-960:opacity-0 max-960:[transition:opacity_0.25s,transform_0.35s_var(--ease),visibility_0s_0.35s]",
          )}
          id="site-nav"
          aria-label="Primary"
        >
          {NAV.map(({ path, label }) => (
            <RouterLink
              key={path}
              className={link}
              to={path}
              aria-current={pathname === path ? "page" : undefined}
              onClick={closeMenu}
            >
              {label}
            </RouterLink>
          ))}
        </nav>
        <ButtonLink
          variant={overPhoto ? "over" : "line"}
          small
          className="justify-self-end max-960:hidden"
          href={LINKS.repo}
        >
          <GitHubIcon />
          GitHub
        </ButtonLink>
        <button
          className="hidden max-960:-mr-2.5 max-960:inline-grid max-960:size-11 max-960:cursor-pointer max-960:place-content-center max-960:gap-1.5 max-960:rounded-xl max-960:bg-transparent max-960:[border:0]"
          type="button"
          aria-controls="site-nav"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="sr-only">Menu</span>
          <i
            className={cx(bar(overPhoto), menuOpen && "max-960:[transform:translateY(3.75px)_rotate(45deg)]")}
            aria-hidden="true"
          />
          <i
            className={cx(bar(overPhoto), menuOpen && "max-960:[transform:translateY(-3.75px)_rotate(-45deg)]")}
            aria-hidden="true"
          />
        </button>
      </div>
    </header>
  );
}

/** A primary nav link: a pill on desktop, a full-width row in the drop-down menu. Over the hero it's white. */
const navLink = (over: boolean): string =>
  cx(
    "rounded-[999px] px-3.5 py-2 text-[15px] [transition:color_0.2s,background-color_0.2s]",
    "max-960:rounded-none max-960:border-b max-960:border-b-line max-960:px-0 max-960:py-3.5 max-960:text-[18px] max-960:aria-[current=page]:bg-transparent",
    over
      ? "text-white hover:bg-[rgb(255_255_255/0.12)] aria-[current=page]:bg-[rgb(255_255_255/0.12)]"
      : "text-mute hover:text-ink aria-[current=page]:bg-sunk aria-[current=page]:text-ink max-960:text-ink",
  );

/** One line of the menu icon; the two cross into an X while the menu is open. */
const bar = (over: boolean): string =>
  cx(
    "max-960:block max-960:h-[1.5px] max-960:w-5 max-960:[transition:transform_0.3s_var(--ease)]",
    over ? "bg-white" : "max-960:bg-ink",
  );
