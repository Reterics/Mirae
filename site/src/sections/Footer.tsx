import { Brand } from "../components/Brand";
import { Link } from "../components/Link";
import { DOC_LINKS } from "../content";
import { SITE } from "../site";

export function Footer() {
  return (
    <footer className="wrap grid grid-cols-[1fr_auto] gap-x-12 gap-y-7 border-t border-t-line pt-12 pb-10 max-560:grid-cols-1">
      <div className="grid gap-2.5">
        <Brand />
        <p className="text-[14px] text-mute">{SITE.tagline}</p>
      </div>
      <nav
        className="flex flex-wrap items-center gap-x-[26px] gap-y-2 text-[15px] text-mute max-560:gap-x-5 max-560:gap-y-0"
        aria-label="Documentation"
      >
        {DOC_LINKS.map(({ label, href }) => (
          <Link key={label} className="hover:text-ink max-560:py-3" href={href}>
            {label}
          </Link>
        ))}
      </nav>
      <p className="col-[1/-1] font-mono text-[12px] leading-[1.6] font-medium text-mute">
        Product images are rendered in Blender from the exact printable model; the Raspberry Pi 5 in the cutaway is
        Raspberry Pi Ltd&apos;s official 3D model (MIT). The family illustration and the printing and floor footage are
        AI-generated.
      </p>
    </footer>
  );
}
