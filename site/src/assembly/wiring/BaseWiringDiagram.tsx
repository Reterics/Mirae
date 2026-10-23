/** Step 17: the base's power and motor wiring. Part images identify hardware; ports are logical, not pad positions. */
import { useId } from "react";

import { media } from "../../lib";
import { Wire } from "./symbols";

const NAME = "fill-ink font-sans";
const MONO = "fill-mute font-mono";
const COLORS = {
  pack: "#b43c35",
  switched: "#c05200",
  common: "#45403a",
  logic: "#0072b2",
  logicReturn: "#626b12",
  motor: "#8e44ad",
  motorReturn: "#008568",
  left1: "#0072b2",
  left2: "#c03665",
  right1: "#485ac7",
  right2: "#9b452e",
} as const;

type Icon = "pack" | "switch" | "charger" | "converter" | "driver" | "motor" | "capacitor";
interface Card {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  sub: string;
  icon: Icon;
}
interface Port {
  card: string;
  side: "L" | "R";
  y: number;
  label: string;
}

const CARDS: Record<string, Card> = {
  pack: { x: 40, y: 120, w: 280, h: 210, title: "2S2P pack + BMS", sub: "HX-2S-JH20 · 6.0–8.4 V", icon: "pack" },
  switch: { x: 440, y: 120, w: 220, h: 210, title: "SL 19123", sub: "Main power switch", icon: "switch" },
  xl: { x: 800, y: 120, w: 260, h: 240, title: "XL6009-UD", sub: "Set output to 6.0 V", icon: "converter" },
  charger: { x: 40, y: 540, w: 280, h: 220, title: "USBC-2S-LI-BOOST", sub: "USB-C 5 V input", icon: "charger" },
  sz: { x: 440, y: 540, w: 240, h: 230, title: "SZ-08CV", sub: "Set output to 5.1 V", icon: "converter" },
  driver: { x: 900, y: 540, w: 220, h: 260, title: "TB6612FNG", sub: "HW-166 motor driver", icon: "driver" },
  left: { x: 1210, y: 540, w: 180, h: 180, title: "Left N20E", sub: "Driver channel A", icon: "motor" },
  right: { x: 1210, y: 800, w: 180, h: 180, title: "Right N20E", sub: "Driver channel B", icon: "motor" },
  cap: { x: 900, y: 870, w: 220, h: 150, title: "1000 µF / 10 V", sub: "Close to the driver", icon: "capacitor" },
};

const PORTS: Record<string, Port> = {
  "pack+": { card: "pack", side: "R", y: 210, label: "P+" },
  "pack−": { card: "pack", side: "R", y: 260, label: "P−" },
  "switch-in": { card: "switch", side: "L", y: 210, label: "from P+" },
  "switch-out": { card: "switch", side: "R", y: 210, label: "to rails" },
  "charge+": { card: "charger", side: "R", y: 610, label: "+" },
  "charge−": { card: "charger", side: "R", y: 650, label: "−" },
  "xl-in+": { card: "xl", side: "L", y: 210, label: "IN+" },
  "xl-in−": { card: "xl", side: "L", y: 250, label: "IN−" },
  "xl-out+": { card: "xl", side: "R", y: 210, label: "OUT+" },
  "xl-out−": { card: "xl", side: "R", y: 250, label: "OUT−" },
  "xl-out−2": { card: "xl", side: "R", y: 285, label: "" },
  "xl-out−3": { card: "xl", side: "R", y: 320, label: "" },
  "sz-in+": { card: "sz", side: "L", y: 590, label: "VIN+" },
  "sz-in−": { card: "sz", side: "L", y: 630, label: "VIN−" },
  "sz-out+": { card: "sz", side: "R", y: 590, label: "Vout+" },
  "sz-out−": { card: "sz", side: "R", y: 630, label: "Vout−" },
  vm: { card: "driver", side: "L", y: 590, label: "VM" },
  gnd1: { card: "driver", side: "L", y: 630, label: "GND" },
  gnd2: { card: "driver", side: "L", y: 670, label: "GND" },
  gnd3: { card: "driver", side: "L", y: 710, label: "GND" },
  ao1: { card: "driver", side: "R", y: 590, label: "AO1" },
  ao2: { card: "driver", side: "R", y: 630, label: "AO2" },
  bo1: { card: "driver", side: "R", y: 670, label: "BO1" },
  bo2: { card: "driver", side: "R", y: 710, label: "BO2" },
  "left+": { card: "left", side: "L", y: 590, label: "1 · Motor+" },
  "left−": { card: "left", side: "L", y: 630, label: "6 · Motor−" },
  "right+": { card: "right", side: "L", y: 850, label: "1 · Motor+" },
  "right−": { card: "right", side: "L", y: 890, label: "6 · Motor−" },
  "cap+": { card: "cap", side: "L", y: 930, label: "+" },
  "cap−": { card: "cap", side: "L", y: 970, label: "−" },
};

function terminal(id: string) {
  const p = PORTS[id];
  const c = p && CARDS[p.card];
  if (!p || !c) throw new Error(`No base wiring terminal ${id}`);
  return { x: p.side === "L" ? c.x : c.x + c.w, y: p.y };
}

// Each entry is one wire between named terminals; waypoints keep it clear of part bodies.
const CONNECTIONS: { from: string; to: string; via?: string; color: string }[] = [
  { from: "pack+", to: "switch-in", color: COLORS.pack },
  { from: "charge+", to: "pack+", via: "H350 V210", color: COLORS.pack },
  { from: "charge−", to: "pack−", via: "H380 V260", color: COLORS.common },
  { from: "switch-out", to: "xl-in+", color: COLORS.switched },
  { from: "switch-out", to: "sz-in+", via: "H710 V480 H410 V590", color: COLORS.switched },
  { from: "pack−", to: "xl-in−", via: "H380 V430 H750 V250", color: COLORS.common },
  { from: "pack−", to: "sz-in−", via: "H380 V630", color: COLORS.common },
  { from: "xl-out+", to: "vm", via: "H1130 V460 H840 V590", color: COLORS.motor },
  { from: "xl-out−", to: "gnd1", via: "H1155 V480 H815 V630", color: COLORS.motorReturn },
  { from: "xl-out−2", to: "gnd2", via: "H1175 V500 H790 V670", color: "#626b12" },
  { from: "xl-out−3", to: "gnd3", via: "H1195 V520 H765 V710", color: "#9b452e" },
  { from: "vm", to: "cap+", via: "H840 V930", color: COLORS.motor },
  { from: "gnd1", to: "cap−", via: "H815 V970", color: COLORS.motorReturn },
  { from: "ao1", to: "left+", color: COLORS.left1 },
  { from: "ao2", to: "left−", color: COLORS.left2 },
  { from: "bo1", to: "right+", via: "H1160 V850", color: COLORS.right1 },
  { from: "bo2", to: "right−", via: "H1185 V890", color: COLORS.right2 },
];

function PartCard({ card: c }: { card: Card }) {
  const imageName = c.icon === "converter" ? (c.title === "SZ-08CV" ? "sz08cv" : "xl6009") : c.icon;
  const width = c.icon === "pack" ? 210 : c.icon === "motor" ? 140 : c.w - 120;
  const imageHeight = c.icon === "motor" ? 60 : c.icon === "capacitor" ? 75 : 115;
  return (
    <g>
      <rect className="fill-surface stroke-line-strong" x={c.x} y={c.y} width={c.w} height={c.h} rx={12} />
      <text className={NAME} x={c.x + 16} y={c.y + 24} fontSize={18} fontWeight={600}>
        {c.title}
      </text>
      <text className={MONO} x={c.x + 16} y={c.y + c.h - 12} fontSize={12}>
        {c.sub}
      </text>
      <image
        aria-hidden="true"
        href={media(c.icon === "pack" ? "assembly/pack.webp" : `wiring/${imageName}.webp`)}
        x={c.x + (c.w - width) / 2}
        y={c.y + (c.icon === "motor" ? 80 : 54)}
        width={width}
        height={imageHeight}
      />
    </g>
  );
}

export function BaseWiringDiagram({ className }: { className: string }) {
  const id = useId();
  return (
    <svg className={className} viewBox="0 0 1420 1140" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>Step 17: base power and motor wiring</title>
      <desc id={`${id}-desc`}>
        BMS P+ feeds the main switch, then both converters. The charger connects directly to BMS P+ and P−. Both
        converter input returns meet at BMS P−. XL6009 output supplies driver VM and all three driver grounds; the
        capacitor is across VM and ground. Channel A drives the left motor, channel B the right. SZ-08CV output, driver
        logic and encoder connections continue in step 22. Terminal positions are diagrammatic; check the markings on
        each board.
      </desc>
      <text className={NAME} x={40} y={45} fontSize={25} fontWeight={600}>
        Wire the base
      </text>
      <text className={MONO} x={40} y={73} fontSize={14}>
        One line per wire · bars share a terminal · dots join, crossings do not
      </text>
      {Object.entries(CARDS).map(([key, card]) => (
        <PartCard key={key} card={card} />
      ))}
      {CONNECTIONS.map(({ from, to, via, color }) => {
        const a = terminal(from);
        const b = terminal(to);
        return (
          <g key={`${from}-${to}`}>
            <title>
              {from} → {to}
            </title>
            <Wire color={color} d={`M${a.x} ${a.y} ${via ?? ""} H${b.x} V${b.y}`} />
          </g>
        );
      })}
      {/* Outputs continue upstairs in step 22; VIN− and Vout− are never bridged here. */}
      <Wire color={COLORS.logic} d="M680 590 H725 V850 H680" />
      <Wire color={COLORS.logicReturn} d="M680 630 H700 V890 H680" />
      <text className={NAME} x={445} y={854} fontSize={15}>
        5.1 V → Pi / amp / HAT
      </text>
      <text className={NAME} x={445} y={894} fontSize={15}>
        Return → SZ Vout−
      </text>
      <text className={MONO} x={445} y={925} fontSize={12}>
        Connect upstairs in step 22.
      </text>
      <text className={MONO} x={445} y={945} fontSize={12}>
        Keep VIN− and Vout− separate.
      </text>
      {[
        [350, 210, COLORS.pack],
        [380, 260, COLORS.common],
        [380, 430, COLORS.common],
        [710, 210, COLORS.switched],
        [840, 590, COLORS.motor],
        [815, 630, COLORS.motorReturn],
        [380, 630, COLORS.common],
      ].map(([x, y, color]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={4.5} fill={String(color)} />
      ))}
      <path className="stroke-ink" strokeWidth={3.2} d="M1060 247 V323" />
      {Object.entries(PORTS).map(([key, p]) => {
        const { x, y } = terminal(key);
        return (
          <g key={key}>
            <circle className="fill-surface stroke-ink" cx={x} cy={y} r={3.5} strokeWidth={1.3} />
            <text
              className={NAME}
              x={x + (p.side === "L" ? 10 : -10)}
              y={y - 4}
              textAnchor={p.side === "L" ? "start" : "end"}
              fontSize={13}
              fontWeight={600}
            >
              {p.label}
            </text>
          </g>
        );
      })}
      <text className={MONO} x={60} y={300} fontSize={12}>
        Pack + BMS already assembled.
      </text>
      <text className={MONO} x={460} y={300} fontSize={12}>
        Use common + one throw.
      </text>
      <text className={MONO} x={820} y={328} fontSize={12}>
        EN left open.
      </text>
      <text className={MONO} x={60} y={730} fontSize={12}>
        Charges with switch off.
      </text>
      <text className={MONO} x={920} y={772} fontSize={12}>
        Logic → step 22.
      </text>
      <text className={MONO} x={1225} y={690} fontSize={11}>
        Encoder → step 22.
      </text>
      <text className={MONO} x={1225} y={950} fontSize={11}>
        Encoder → step 22.
      </text>
      <text className={MONO} x={40} y={1055} fontSize={13}>
        From docs/wiring.md (proposed, not yet verified on a robot). Set both outputs before connecting loads.
      </text>
      <text className={MONO} x={40} y={1080} fontSize={13}>
        Motor current returns to XL6009 OUT−, never through a Pi GND pin. The common input ground is BMS P−.
      </text>
      <text className={MONO} x={40} y={1105} fontSize={13}>
        Part images and terminal positions are illustrative. Check board markings; colors help trace wires.
      </text>
    </svg>
  );
}
