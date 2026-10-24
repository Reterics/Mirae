/**
 * The robot's wiring as a wiring diagram: every wire is its own line, from the pin it starts on to
 * the point it lands on, so a builder can wire from it one wire at a time. What goes where comes only
 * from docs/wiring.md (its GPIO table and the "Wire goes to" column of its power table, via pins.ts);
 * a pin the doc doesn't place fails the build instead of being drawn with a guess.
 *
 * The Pi's 40-pin header is drawn as one terminal column in pin order, the way connectors are drawn on
 * wiring diagrams, with a 2 × 20 locator beside it; its labels are the Raspberry Pi pinout's. Where
 * several wires land on one point (a converter terminal, or a splice) that point is drawn as a bar with
 * one landing per wire. Lines that cross never join.
 */
import { LINKS, PI_HEADER, PI_LABELS, WIRES } from "./pins";
import { bodyH, PIN, type PartDef, ROW } from "./geometry";
import { NoConnect, Part, PolarCap, Wire } from "./symbols";

const MONO = "fill-mute font-mono";
const NAME = "fill-ink font-sans";

type Pt = [number, number];
type ChannelId = "main" | "power";

// ------------------------------------------------------------------ parts
const HEADER_X = 60;
const COL1 = 780; // left edge of the module column
const COL1_W = 140;
const COL2 = 1100; // left edge of the converter column
const WIDTH = 1420;

const piHeader: PartDef = {
  ref: "J1 · Raspberry Pi 5",
  value: "40-pin GPIO header, in pin order",
  x: HEADER_X,
  y: 110,
  w: 170,
  rows: 40,
  pins: PI_LABELS.map((name, i) => ({ name, side: "R" as const, row: i, number: String(i + 1) })),
};

const left = (names: string[], from = 0) => names.map((name, i) => ({ name, side: "L" as const, row: from + i }));
const right = (names: string[], from = 0) => names.map((name, i) => ({ name, side: "R" as const, row: from + i }));

/** An N20E gear motor's 6-wire cable: encoder wires toward the Pi, motor wires toward the driver. */
const n20 = (ref: string): PartDef => ({
  ref,
  value: "N20E, 6-wire cable",
  x: COL1,
  y: 0,
  w: COL1_W,
  rows: 4,
  pins: [
    ...["Encoder+", "C1", "C2", "GND"].map((name, i) => ({ name, side: "L" as const, row: i, number: String(i + 2) })),
    { name: "Motor+", side: "R", row: 0, number: "1" },
    { name: "Motor−", side: "R", row: 3, number: "6" },
  ],
});

/**
 * Every drawn part, by its module name in docs/wiring.md, pin names as printed on each board. A pin
 * that takes several wires leaves the rows under it free for their landings (SLOTS). The module
 * column's parts are stacked in this order; y is filled in below.
 */
const PARTS: Record<string, PartDef> = {
  "SZ-08CV": {
    ref: "U5 · SZ-08CV",
    value: "converter, set to 5.1 V",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 8,
    pins: [{ name: "Vout+", side: "L", row: 0 }, { name: "Vout−", side: "L", row: 4 }, ...right(["VIN+", "VIN−"])],
  },
  VL53L1X: {
    ref: "U2 · VL53L1X",
    value: "distance sensor (Adafruit #3967)",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 6,
    pins: left(["VIN", "GND", "SCL", "SDA", "GPIO1", "XSHUT"]),
  },
  "Motor L": n20("J2 · Motor L"),
  "Motor R": n20("J3 · Motor R"),
  TB6612: {
    ref: "U1 · TB6612FNG",
    value: "motor driver (HW-166)",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 9,
    pins: [
      ...left(["PWMA", "AIN2", "AIN1", "STBY", "BIN1", "BIN2", "PWMB", "VCC", "GND"]),
      { name: "VM", side: "R", row: 0 },
      { name: "GND", side: "R", row: 2 },
      ...right(["AO1", "AO2", "BO2", "BO1", "GND"], 4),
    ],
  },
  INMP441: {
    ref: "U3 · INMP441",
    value: "I2S microphone",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 6,
    pins: left(["L/R", "WS", "SCK", "SD", "VDD", "GND"]),
  },
  MAX98357: {
    ref: "U4 · MAX98357",
    value: "I2S amplifier",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 7,
    pins: [...left(["LRC", "BCLK", "DIN", "GAIN", "SD", "GND", "Vin"]), ...right(["+"], 2), ...right(["−"], 4)],
  },
  "AI HAT+ 2": {
    ref: "U6 · AI HAT+ 2 (optional)",
    value: "its own 40-pin header, under the Pi",
    x: COL1,
    y: 0,
    w: COL1_W,
    rows: 2,
    pins: [
      { name: "5V", side: "L", row: 0, number: "2" },
      { name: "GND", side: "L", row: 1, number: "6" },
    ],
  },
  "XL6009-UD": {
    ref: "U7 · XL6009-UD",
    value: "converter, set to 12.0 V",
    x: COL2,
    y: 0,
    w: 110,
    rows: 5,
    pins: [{ name: "OUT+", side: "L", row: 0 }, { name: "OUT−", side: "L", row: 2 }, ...right(["IN+", "IN−", "EN"])],
  },
};

function part(name: string): PartDef {
  const p = PARTS[name];
  if (!p) throw new Error(`no part ${name}`);
  return p;
}

/** Landings a pin has room for, when it takes more than one wire. */
const SLOTS: Record<string, number> = {
  "SZ-08CV|Vout+|0": 4,
  "SZ-08CV|Vout−|0": 4,
  "TB6612|VM|0": 2,
  "TB6612|GND|1": 2,
  "XL6009-UD|OUT−|0": 3,
};

// ------------------------------------------------------------------ wires, from docs/wiring.md
/** A point wires land on: "J1|n", "<module>|<pin>|<nth>", "SP|<name>" or "Capacitor|±|0". */
type Base = string;
interface Edge {
  a: Base;
  b: Base;
}
interface Splice {
  name: string;
  note: string;
}

const pinCount = (module: string, pin: string) =>
  module === "Capacitor" ? 1 : (PARTS[module]?.pins.filter((q) => q.name === pin).length ?? 0);

function moduleBase(module: string, pin: string, nth = 0): Base {
  if (module !== "Capacitor" && pinCount(module, pin) <= nth)
    throw new Error(`the wiring diagram has no ${module} ${pin}`);
  return `${module}|${pin}|${nth}`;
}

/** Where a "Wire goes to" cell sends a wire: header pins, a splice, a part's terminal, or off this sheet. */
function landing(at: string, from: string): { bases: Base[]; splice?: [string, number]; offSheet?: string } {
  const sp = /^splice "([^"]+)" \(Pi header pin (\d+)\)$/.exec(at);
  if (sp) return { bases: [`SP|${sp[1] ?? ""}`], splice: [sp[1] ?? "", Number(sp[2])] };
  const pins = /^Pi header pins? ([\d and]+)$/.exec(at);
  if (pins)
    return {
      bases: (pins[1] ?? "")
        .split(/\D+/)
        .filter(Boolean)
        .map((n) => `J1|${n}`),
    };
  const motor = /^(Motor [LR]), (.+)$/.exec(at);
  if (motor) return { bases: [moduleBase(motor[1] ?? "", motor[2] ?? "")] };
  const cut = at.lastIndexOf(" ");
  const [module, pin] = [at.slice(0, cut), at.slice(cut + 1)];
  if (module in PARTS) {
    // the capacitor sits across VM and the GND pin beside it; a wire to "TB6612 GND" from anything
    // else means each of the driver's GND pins (each has its own row in the doc's table)
    if (from === "Capacitor" && module === "TB6612" && pin === "GND") return { bases: [moduleBase(module, pin, 1)] };
    return { bases: Array.from({ length: pinCount(module, pin) }, (_, k) => moduleBase(module, pin, k)) };
  }
  return { bases: [], offSheet: at };
}

function buildWiring() {
  const edges: Edge[] = [];
  const seen = new Set<string>();
  const wire = (a: Base, b: Base) => {
    const id = [a, b].sort().join(" ~ ");
    if (!seen.has(id)) {
      seen.add(id);
      edges.push({ a, b });
    }
  };
  const splices = new Map<string, Splice>();

  // GPIO wires; a header pin shared by two modules needs a splice the doc doesn't place yet
  for (const pin of new Set(WIRES.map((w) => w.pin))) {
    const on = WIRES.filter((w) => w.pin === pin);
    if (on.length === 1) {
      const [w] = on;
      if (w) wire(`J1|${pin}`, moduleBase(w.module, w.modulePin));
      continue;
    }
    const name = on[0]?.fn ?? `pin ${pin}`;
    splices.set(name, { name, note: "near the Pi GPIO breakout" });
    wire(`J1|${pin}`, `SP|${name}`);
    for (const w of on) wire(moduleBase(w.module, w.modulePin), `SP|${name}`);
  }

  const offSheet: { base: Base; text: string }[] = [];
  const noConnect: Base[] = [];
  for (const l of LINKS) {
    if (l.to.startsWith("Speaker")) continue; // the amplifier's screw terminal, drawn with the speaker
    if (l.module !== "Capacitor" && !(l.module in PARTS))
      throw new Error(`docs/wiring.md names ${l.module}, which the wiring diagram doesn't draw`);
    const count = Math.max(1, pinCount(l.module, l.modulePin));
    for (let nth = 0; nth < count; nth++) {
      const from = moduleBase(l.module, l.modulePin, nth);
      if (l.to === "not connected") {
        noConnect.push(from);
        continue;
      }
      if (!l.at) throw new Error(`docs/wiring.md doesn't say where ${l.module} ${l.modulePin}'s wire goes`);
      const d = landing(l.at, l.module);
      if (d.splice) {
        const [name, pin] = d.splice;
        splices.set(name, { name, note: `from J1 pin ${pin}` });
        wire(`SP|${name}`, `J1|${pin}`);
      }
      for (const b of d.bases) wire(from, b);
      if (d.offSheet) offSheet.push({ base: from, text: d.offSheet });
    }
  }
  return { edges, splices: [...splices.values()], offSheet, noConnect };
}

// ------------------------------------------------------------------ layout
const WIRING = buildWiring();

/** Wires per landing point, which sets how tall each splice is and checks the parts' room. */
const degree = new Map<Base, number>();
for (const e of WIRING.edges) for (const b of [e.a, e.b]) degree.set(b, (degree.get(b) ?? 0) + 1);
for (const [b, k] of degree) {
  if (b.startsWith("J1|") && k > 1) throw new Error(`docs/wiring.md puts ${k} wires on header pin ${b.slice(3)}`);
  if (!b.startsWith("J1|") && !b.startsWith("SP|") && k > (SLOTS[b] ?? 1))
    throw new Error(`${b} takes ${k} wires; give it room in SLOTS`);
}

/** Splices, drawn as a bar in the module column next to what they feed. */
const SPLICE_AT: Record<string, string> = {
  "3V3 sensor": "VL53L1X",
  "3V3 drive": "TB6612",
  "I2S BCLK": "INMP441",
  "I2S LRCLK": "INMP441",
};
interface SpliceBox {
  splice: Splice;
  ref: string;
  y: number;
  slots: number;
}

/** Stack the module column top to bottom: parts, with each splice placed just above the part it feeds. */
const COLUMN = (() => {
  const order = ["SZ-08CV", "VL53L1X", "Motor L", "Motor R", "TB6612", "INMP441", "MAX98357", "AI HAT+ 2"];
  const splices: SpliceBox[] = [];
  let y = 120;
  const snap = (v: number) => Math.ceil(v / 20) * 20; // module rows stay between header rows
  let n = 1;
  for (const module of order) {
    for (const s of WIRING.splices.filter((x) => SPLICE_AT[x.name] === module)) {
      const slots = degree.get(`SP|${s.name}`) ?? 0;
      splices.push({ splice: s, ref: `SP${n++}`, y, slots });
      y = snap(y + slots * ROW + 40);
    }
    const p = PARTS[module];
    if (!p) throw new Error(`no part ${module}`);
    p.y = y + 20;
    y = snap(p.y + bodyH(p) + 60);
  }
  for (const s of WIRING.splices) if (!SPLICE_AT[s.name]) throw new Error(`no place for splice ${s.name}`);
  const tb = part("TB6612");
  const dsn = part("XL6009-UD");
  dsn.y = tb.y + 10; // off the driver's rows, so no two wires share a line
  return { splices, bottom: y };
})();
const CAP = (() => {
  const dsn = part("XL6009-UD");
  const plus = dsn.y + bodyH(dsn) + 30;
  return { x: COL2 + 40, plus, minus: plus + 80 };
})();

interface Point {
  at: Pt;
  channel: ChannelId;
}
/** Where landing `slot` of a point is, and which channel its wire runs in. */
function point(base: Base, slot = 0): Point {
  const [kind = "", pin = "", nthS = "0"] = base.split("|");
  if (kind === "J1") return { at: [piHeader.x + piHeader.w + PIN, piHeader.y + Number(pin) * ROW], channel: "main" };
  if (kind === "SP") {
    const s = COLUMN.splices.find((x) => x.splice.name === pin);
    if (!s) throw new Error(`no splice ${pin}`);
    return { at: [COL1 - PIN, s.y + (slot + 1) * ROW], channel: "main" };
  }
  if (kind === "Capacitor") return { at: [COL2 - PIN, pin === "+" ? CAP.plus : CAP.minus], channel: "power" };
  const p = PARTS[kind];
  const q = p?.pins.filter((x) => x.name === pin)[Number(nthS)];
  if (!p || !q) throw new Error(`no ${base}`);
  const y = p.y + (q.row + 1 + slot) * ROW;
  const atLeft = q.side === "L";
  const channel: ChannelId = atLeft && p.x !== COL2 ? "main" : "power";
  return { at: [atLeft ? p.x - PIN : p.x + p.w + PIN, y], channel };
}

/** One drawn wire: its two ends (in one channel), and the path out of the channel if it has to leave it. */
interface Run {
  edge: Edge;
  ends: [Pt, Pt];
  channel: ChannelId;
  detour?: Pt[];
}

function runs(): Run[] {
  // a point's landings go to its wires in order of where their other ends sit, so they don't cross
  const otherY = (e: Edge, b: Base) => point(e.a === b ? e.b : e.a).at[1];
  const slotOf = new Map<Edge, [number, number]>();
  for (const b of degree.keys()) {
    const mine = WIRING.edges.filter((e) => e.a === b || e.b === b).sort((x, y) => otherY(x, b) - otherY(y, b));
    mine.forEach((e, i) => {
      const s = slotOf.get(e) ?? [0, 0];
      s[e.a === b ? 0 : 1] = i;
      slotOf.set(e, s);
    });
  }
  return WIRING.edges.map((e) => {
    const [sa, sb] = slotOf.get(e) ?? [0, 0];
    const pa = point(e.a, sa);
    const pb = point(e.b, sb);
    if (pa.channel === pb.channel) return { edge: e, ends: [pa.at, pb.at], channel: pa.channel };
    // a module-side pin on a motor-supply wire: round the bottom of its part into the other channel
    const [inside, outside] = pa.channel === "main" ? [pa, pb] : [pb, pa];
    const part = PARTS[(pa.channel === "main" ? e.a : e.b).split("|")[0] ?? ""];
    if (!part) throw new Error(`can't route ${e.a} to ${e.b}`);
    const below = part.y + bodyH(part) + 20;
    const edge: Pt = [part.x + part.w + PIN, below];
    return {
      edge: e,
      ends: [edge, outside.at],
      channel: outside.channel,
      detour: [inside.at, [inside.at[0] - 14, inside.at[1]], [inside.at[0] - 14, below], edge],
    };
  });
}

// ------------------------------------------------------------------ tracks
const CHANNELS: Record<ChannelId, { from: number; to: number }> = {
  main: { from: piHeader.x + piHeader.w + PIN, to: COL1 - PIN },
  power: { from: COL1 + COL1_W + PIN, to: COL2 - PIN },
};

interface Seg {
  h: { y: number; x0: number; x1: number }[];
  v: { x: number; y0: number; y1: number };
}
const seg = (r: Run, lane: number): Seg => ({
  h: r.ends.map(([x, y]) => ({ y, x0: Math.min(x, lane), x1: Math.max(x, lane) })),
  v: { x: lane, y0: Math.min(r.ends[0][1], r.ends[1][1]), y1: Math.max(r.ends[0][1], r.ends[1][1]) },
});

/** Crossings between two wires, and a heavy cost for lines that would run on or touch each other. */
function cost(a: Seg, b: Seg): number {
  let c = 0;
  const cross = (h: Seg["h"][number], v: Seg["v"]) => v.x > h.x0 && v.x < h.x1 && h.y > v.y0 && h.y < v.y1;
  const touch = (h: Seg["h"][number], v: Seg["v"]) =>
    v.x >= h.x0 && v.x <= h.x1 && h.y >= v.y0 && h.y <= v.y1 && !cross(h, v);
  for (const [p, q] of [
    [a, b],
    [b, a],
  ] as const)
    for (const h of p.h) {
      if (cross(h, q.v)) c++;
      if (touch(h, q.v)) c += 1000;
    }
  for (const ha of a.h)
    for (const hb of b.h) if (ha.y === hb.y && Math.min(ha.x1, hb.x1) >= Math.max(ha.x0, hb.x0)) c += 1000;
  return c;
}

/** Give every wire in a channel its own track, swapping tracks while that removes crossings. Deterministic. */
function assignTracks(list: Run[], ch: { from: number; to: number }): number[] {
  const n = list.length;
  const pitch = Math.min(12, (ch.to - ch.from - 16) / Math.max(1, n - 1));
  const laneX = (i: number) => ch.from + 8 + i * pitch;
  const mid = (r: Run | undefined) => (r ? (r.ends[0][1] + r.ends[1][1]) / 2 : 0);
  const order = list.map((_, i) => i).sort((a, b) => mid(list[a]) - mid(list[b]));
  const total = () => {
    const s = order.flatMap((ix, i) => {
      const r = list[ix];
      return r ? [seg(r, laneX(i))] : [];
    });
    let c = 0;
    s.forEach((x, i) => s.slice(i + 1).forEach((y) => (c += cost(x, y))));
    return c;
  };
  const swap = (i: number, j: number) => {
    const t = order[i] ?? 0;
    order[i] = order[j] ?? 0;
    order[j] = t;
  };
  let best = total();
  for (let improved = true; improved;) {
    improved = false;
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        swap(i, j);
        const c = total();
        if (c < best) {
          best = c;
          improved = true;
        } else swap(i, j);
      }
  }
  const lanes = new Array<number>(n);
  order.forEach((ix, i) => (lanes[ix] = laneX(i)));
  return lanes;
}

// Alternate hues along neighboring tracks; these are tracing aids, not cable insulation colors.
const WIRE_COLORS = ["#0072b2", "#c05200", "#8e44ad", "#008568", "#c03665", "#626b12", "#485ac7", "#9b452e"];

const LAYOUT = (() => {
  const all = runs();
  const routed = (["main", "power"] as const).flatMap((id) => {
    const list = all.filter((r) => r.channel === id);
    const lanes = assignTracks(list, CHANNELS[id]);
    const ordered = [...lanes].sort((a, b) => a - b);
    return list.map((r, i) => {
      const lane = lanes[i] ?? 0;
      return { run: r, lane, color: WIRE_COLORS[ordered.indexOf(lane) % WIRE_COLORS.length] ?? WIRE_COLORS[0] };
    });
  });
  return { routed };
})();

function leadColor(base: Base) {
  return LAYOUT.routed.find(({ run }) => run.edge.a === base || run.edge.b === base)?.color;
}

// ------------------------------------------------------------------ drawing
function OffSheet({ at: [x, y], text }: { at: Pt; text: string }) {
  return (
    <g>
      <path className="fill-none stroke-ink" strokeWidth={1.4} d={`M${x} ${y} h16 m-6 -5 l6 5 l-6 5`} />
      <text className={MONO} x={x + 22} y={y + 4} fontSize={11}>
        to {text}
      </text>
    </g>
  );
}

/** A landing bar on a pin that takes several wires: the pin's stub end, stretched down over its landings. */
function Bar({ at: [x, y], slots }: { at: Pt; slots: number }) {
  return <path className="fill-none stroke-ink" strokeWidth={3.2} d={`M${x} ${y - 3} V${y + (slots - 1) * ROW + 3}`} />;
}

/** The header as the pinout chart shows it: 2 × 20, odd pins on the left, pin 1 at the top; wired pins filled. */
function Locator({ x, y }: { x: number; y: number }) {
  const wired = new Set(WIRING.edges.flatMap((e) => [e.a, e.b]).filter((b) => b.startsWith("J1|")));
  return (
    <g>
      <text className={NAME} x={x} y={y} fontSize={12} fontWeight={600}>
        J1 on the Pi
      </text>
      <text className={MONO} x={x} y={y + 15} fontSize={10.5}>
        as on the pinout chart
      </text>
      <rect
        className="fill-surface stroke-ink"
        strokeWidth={1.2}
        x={x}
        y={y + 26}
        width={44}
        height={20 * 12 + 8}
        rx={4}
      />
      {PI_HEADER.map((_, i) => {
        const cx = x + (i % 2 === 0 ? 14 : 30);
        const cy = y + 36 + Math.floor(i / 2) * 12;
        return (
          <circle
            key={i}
            className={wired.has(`J1|${i + 1}`) ? "fill-ink stroke-ink" : "fill-surface stroke-ink"}
            strokeWidth={1}
            cx={cx}
            cy={cy}
            r={3.6}
          />
        );
      })}
      {[
        ["1", -8, 0],
        ["2", 52, 0],
        ["39", -8, 19],
        ["40", 52, 19],
      ].map(([t, dx, row]) => (
        <text
          key={t}
          className={MONO}
          x={x + Number(dx)}
          y={y + 39 + Number(row) * 12}
          fontSize={9.5}
          textAnchor={Number(dx) < 0 ? "end" : "start"}
        >
          {t}
        </text>
      ))}
      <text className={MONO} x={x} y={y + 300} fontSize={10.5}>
        ● wired ○ free
      </text>
    </g>
  );
}

export function WiringDiagram({ className }: { className: string }) {
  const { routed } = LAYOUT;
  const [sx, sy0] = point("MAX98357|+|0").at;
  const [, sy1] = point("MAX98357|−|0").at;
  const spk = { x: sx + 40, y: (sy0 + sy1) / 2 };
  const wiredHeader = new Set(WIRING.edges.flatMap((e) => [e.a, e.b]));
  const height = Math.max(COLUMN.bottom, piHeader.y + bodyH(piHeader)) + 90;

  return (
    <svg className={className} viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label="Wiring diagram">
      <Part p={piHeader} />
      <Locator x={HEADER_X + 40} y={piHeader.y + bodyH(piHeader) + 50} />
      {Object.values(PARTS).map((p) => (
        <Part key={p.ref} p={p} />
      ))}
      {PI_HEADER.map((_, i) =>
        wiredHeader.has(`J1|${i + 1}`) ? null : <NoConnect key={i} at={point(`J1|${i + 1}`).at} />,
      )}
      {WIRING.noConnect.map((b) => (
        <NoConnect key={b} at={point(b).at} />
      ))}

      {routed.map(({ run, lane, color }, i) => (
        <g key={i}>
          <Wire
            color={color}
            d={`M${run.ends[0][0]} ${run.ends[0][1]} H${lane} V${run.ends[1][1]} H${run.ends[1][0]}`}
          />
          {run.detour && (
            <Wire color={color} d={run.detour.map(([x, y], k) => `${k ? "L" : "M"}${x} ${y}`).join(" ")} />
          )}
        </g>
      ))}

      {Object.entries(SLOTS).map(([b, slots]) => (
        <Bar key={b} at={point(b).at} slots={slots} />
      ))}
      {COLUMN.splices.map((s) => (
        <g key={s.ref}>
          <Bar at={point(`SP|${s.splice.name}`).at} slots={s.slots} />
          <text className={NAME} x={COL1 - PIN + 12} y={s.y + ROW + 4} fontSize={13} fontWeight={600}>
            {s.ref} · splice
          </text>
          <text className={MONO} x={COL1 - PIN + 12} y={s.y + ROW + 19} fontSize={11}>
            “{s.splice.name}”, {s.slots} wires
          </text>
          <text className={MONO} x={COL1 - PIN + 12} y={s.y + ROW + 33} fontSize={11}>
            {s.splice.note}
          </text>
        </g>
      ))}
      {WIRING.offSheet.map((o) => (
        <OffSheet key={o.base} at={point(o.base).at} text={o.text} />
      ))}

      {/* C1: + lead and − lead from the channel edge */}
      <Wire color={leadColor("Capacitor|+|0")} d={`M${COL2 - PIN} ${CAP.plus} H${CAP.x} V${CAP.plus + 22}`} />
      <Wire color={leadColor("Capacitor|−|0")} d={`M${COL2 - PIN} ${CAP.minus} H${CAP.x} V${CAP.minus - 22}`} />
      <PolarCap x={CAP.x} top={CAP.plus + 22} bottom={CAP.minus - 22} label="C1 · 1000 µF / 16 V, at the driver" />

      {/* LS1: the speaker on the amplifier's screw terminal */}
      <g>
        <Wire color={WIRE_COLORS[0]} d={`M${sx} ${sy0} H${spk.x} V${spk.y - 8}`} />
        <Wire color={WIRE_COLORS[1]} d={`M${sx} ${sy1} H${spk.x} V${spk.y + 8}`} />
        <path
          className="fill-surface stroke-ink"
          strokeWidth={1.5}
          strokeLinejoin="round"
          d={`M${spk.x} ${spk.y - 12} h10 v24 h-10 Z M${spk.x + 10} ${spk.y - 12} l14 -12 v48 l-14 -12`}
        />
        <text className={NAME} x={spk.x + 32} y={spk.y - 4} fontSize={13} fontWeight={600}>
          LS1
        </text>
        <text className={MONO} x={spk.x + 32} y={spk.y + 12} fontSize={11}>
          speaker
        </text>
      </g>

      <text className={MONO} x={24} y={height - 60} fontSize={12}>
        From docs/wiring.md (proposed, not yet verified on a robot). Every line is one wire; lines that cross are not
        joined.
      </text>
      <text className={MONO} x={24} y={height - 40} fontSize={12}>
        A thick bar is one terminal or splice that several wires land on, one landing per wire. × = not connected. Parts
        show every pin by its printed name, grouped by function.
      </text>
      <text className={MONO} x={24} y={height - 20} fontSize={12}>
        Colors help trace individual wires; they do not specify cable insulation colors.
      </text>
    </svg>
  );
}
