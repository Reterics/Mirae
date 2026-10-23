import type { AnchorHTMLAttributes } from "react";

import { cx, isExternal } from "../lib";
import { buttonClass, type ButtonVariant } from "../ui";

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

/** An anchor that never leaks the opener or referrer to another site. */
export function Link({ href, ...rest }: Props) {
  return <a href={href} rel={isExternal(href) ? "noopener noreferrer" : undefined} {...rest} />;
}

/** A button-styled link. */
export function ButtonLink({
  variant,
  small = false,
  className,
  ...rest
}: Props & { variant: ButtonVariant; small?: boolean }) {
  return <Link className={cx(buttonClass(variant, small), className)} {...rest} />;
}
