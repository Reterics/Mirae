/** Site-wide identity and links, shared by the page and by the build (vite.config.ts injects the <head> tags). */

const NAME = "Mirae";
const TAGLINE = "Simple body. Intelligent behavior.";

export const SITE = {
  name: NAME,
  tagline: TAGLINE,
  title: `${NAME} · ${TAGLINE}`,
  description:
    "Mirae is a small, open and hackable AI companion robot built around a Raspberry Pi 5. Every part of its body prints on an ordinary 220 × 220 printer.",
  shortDescription: "A small, open and hackable AI companion robot built around a Raspberry Pi 5.",
  themeColor: "#f6f3ee",
} as const;

export const REPO = "https://github.com/Reterics/Mirae";

const blob = (path: string): string => `${REPO}/blob/main/${path}`;
const tree = (path: string): string => `${REPO}/tree/main/${path}`;

export const LINKS = {
  repo: REPO,
  stl: tree("cad/stl"),
  partsList: blob("docs/hardware.md#shopping-list"),
  software: blob("docs/software.md"),
  architecture: blob("docs/architecture.md"),
  hardware: blob("docs/hardware.md"),
  wiring: blob("docs/wiring.md"),
  cad: blob("cad/README.md"),
  roadmap: blob("docs/roadmap.md"),
} as const;
