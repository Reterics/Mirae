/**
 * Schematic symbols on a 10-unit grid, drawn the way EDA schematics are: a part is a rectangle with
 * its pin names inside and pin numbers on the stubs outside; rails are power ports, ground is the
 * ground symbol, nets that would cross are joined by name with net flags, unused pins get an ×.
 */
import { bodyH, PIN, type PartDef, ROW } from "./geometry";

const LINE = "fill-none stroke-ink";
const NAME = "fill-ink font-sans";
const NUM = "fill-mute font-mono";

export function Part({ p, children }: { p: PartDef; children?: React.ReactNode }) {
  return (
    <g>
      <text className={NAME} x={p.x} y={p.y - 24} fontSize={13} fontWeight={600}>
        {p.ref}
      </text>
      <text className={NUM} x={p.x} y={p.y - 8} fontSize={11}>
        {p.value}
      </text>
      <rect className="fill-surface stroke-ink" strokeWidth={1.6} x={p.x} y={p.y} width={p.w} height={bodyH(p)} />
      {p.pins.map((q) => {
        const y = p.y + (q.row + 1) * ROW;
        const left = q.side === "L";
        const edge = left ? p.x : p.x + p.w;
        const end = left ? edge - PIN : edge + PIN;
        return (
          <g key={`${q.name}-${q.row}-${q.side}`}>
            <path className={LINE} strokeWidth={1.4} d={`M${edge} ${y} H${end}`} />
            <text
              className={NAME}
              x={left ? edge + 6 : edge - 6}
              y={y + 4}
              fontSize={12}
              textAnchor={left ? "start" : "end"}
            >
              {q.name}
            </text>
            {q.number && (
              <text
                className={NUM}
                x={left ? edge - 5 : edge + 5}
                y={y - 4}
                fontSize={9.5}
                textAnchor={left ? "end" : "start"}
              >
                {q.number}
              </text>
            )}
          </g>
        );
      })}
      {children}
    </g>
  );
}

export function Wire({ d, color }: { d: string; color?: string | undefined }) {
  if (!color) return <path className={LINE} strokeWidth={1.4} strokeLinejoin="miter" d={d} />;
  return (
    <g fill="none" strokeLinejoin="round">
      <path className="stroke-surface" strokeWidth={5} d={d} />
      <path stroke={color} strokeWidth={2.2} d={d} />
    </g>
  );
}

/** A pin left unconnected on purpose. */
export function NoConnect({ at: [x, y] }: { at: [number, number] }) {
  return (
    <path
      className={LINE}
      strokeWidth={1.4}
      d={`M${x - 5} ${y - 5} L${x + 5} ${y + 5} M${x - 5} ${y + 5} L${x + 5} ${y - 5}`}
    />
  );
}

/** A polarised capacitor standing upright between (x, top) and (x, bottom), + at the top. */
export function PolarCap({ x, top, bottom, label }: { x: number; top: number; bottom: number; label: string }) {
  const mid = (top + bottom) / 2;
  return (
    <g>
      <path
        className={LINE}
        strokeWidth={1.4}
        d={`M${x} ${top} V${mid - 4} M${x - 12} ${mid - 4} H${x + 12} M${x} ${mid + 4} V${bottom}`}
      />
      <path className={LINE} strokeWidth={1.8} d={`M${x - 12} ${mid + 7} Q${x} ${mid + 1} ${x + 12} ${mid + 7}`} />
      <text className={NAME} x={x - 18} y={mid - 8} fontSize={11} textAnchor="end">
        +
      </text>
      <text className={NUM} x={x + 18} y={mid + 4} fontSize={11}>
        {label}
      </text>
    </g>
  );
}
