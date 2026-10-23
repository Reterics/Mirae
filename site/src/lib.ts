/**
 * URL of a file in public/media. There is a single HTML page and routes live in the hash, so a
 * path relative to the document works in dev, in the build and in any deploy folder.
 */
export const media = (file: string): string => `media/${file}`;

export const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const isExternal = (href: string): boolean => /^https?:\/\//.test(href);

/** Join class names, skipping falsy ones. */
export const cx = (...names: (string | false | null | undefined)[]): string => names.filter(Boolean).join(" ");
