/**
 * The Pi 5 pin map, read from docs/wiring.md at build time so the diagram can't drift from the doc.
 * One row of its table is one Pi header pin; the "Module pin" cell names one or more module pins
 * ("TB6612 PWMA", "INMP441 SCK, MAX98357 BCLK", "Motor L, C1").
 */
import doc from "../../../../docs/wiring.md?raw";

export interface Wire {
  gpio: number;
  /** Physical pin on the 40-pin header, 1–40. */
  pin: number;
  module: string;
  modulePin: string;
  fn: string;
}

/** The module pins in one table cell: a part without a space ("C1") belongs to the module before it. */
function modulePins(cell: string): { module: string; pin: string }[] {
  const parts: string[] = [];
  for (const part of cell.split(",").map((p) => p.trim())) {
    const last = parts.pop();
    if (last !== undefined && !part.includes(" ")) parts.push(`${last} ${part}`);
    else parts.push(...(last === undefined ? [] : [last]), part);
  }
  return parts.map((p) => {
    const at = p.lastIndexOf(" ");
    return { module: p.slice(0, at), pin: p.slice(at + 1) };
  });
}

function parse(md: string): Wire[] {
  const rows = md
    .split("\n")
    .filter((line) => /^\|[^|]+\|\s*\d+\s*\|\s*\d+\s*\|/.test(line))
    .map((line) => line.split("|").map((c) => c.trim()));
  const wires = rows.flatMap(([, fn = "", gpio = "", pin = "", cell = ""]) =>
    modulePins(cell).map((m) => ({ fn, gpio: Number(gpio), pin: Number(pin), module: m.module, modulePin: m.pin })),
  );
  if (wires.length === 0) throw new Error("docs/wiring.md: no pin table found");
  return wires;
}

export const WIRES: readonly Wire[] = parse(doc);

/** A module pin that isn't on a GPIO: a rail ("3V3", "GND"), another part's pin, or "not connected". */
export interface Link {
  module: string;
  modulePin: string;
  to: string;
  /** The exact point its wire lands on: a header pin, a splice or another part's terminal ("" if none). */
  at: string;
}

function parseLinks(md: string): Link[] {
  const lines = md.split("\n");
  const start = lines.findIndex((l) => /^\|\s*Module pin\s*\|\s*Connects to\s*\|/.test(l));
  if (start < 0) throw new Error("docs/wiring.md: no power and ground table found");
  const links: Link[] = [];
  for (const line of lines.slice(start + 2)) {
    if (!line.startsWith("|")) break;
    const [, cell = "", to = "", at = ""] = line.split("|").map((c) => c.trim());
    for (const m of modulePins(cell)) links.push({ module: m.module, modulePin: m.pin, to, at });
  }
  return links;
}

export const LINKS: readonly Link[] = parseLinks(doc);

/**
 * What each pin of the Raspberry Pi 5's 40-pin header is (the standard Raspberry Pi pinout). The
 * GPIO table in docs/wiring.md is checked against it below, so a typo there fails the build.
 */
export const PI_HEADER: readonly string[] = [
  "3V3", "5V", "GPIO2", "5V", "GPIO3", "GND", "GPIO4", "GPIO14", "GND", "GPIO15",
  "GPIO17", "GPIO18", "GPIO27", "GND", "GPIO22", "GPIO23", "3V3", "GPIO24", "GPIO10", "GND",
  "GPIO9", "GPIO25", "GPIO11", "GPIO8", "GND", "GPIO7", "GPIO0", "GPIO1", "GPIO5", "GND",
  "GPIO6", "GPIO12", "GPIO13", "GND", "GPIO19", "GPIO16", "GPIO26", "GPIO20", "GND", "GPIO21",
]; // prettier-ignore

/** The same 40 pins named the way the Raspberry Pi pinout chart names them, alternate functions included. */
export const PI_LABELS: readonly string[] = [
  "3V3 power", "5V power", "GPIO 2 (SDA)", "5V power", "GPIO 3 (SCL)", "Ground", "GPIO 4 (GPCLK0)",
  "GPIO 14 (TXD)", "Ground", "GPIO 15 (RXD)", "GPIO 17", "GPIO 18 (PCM_CLK)", "GPIO 27", "Ground", "GPIO 22",
  "GPIO 23", "3V3 power", "GPIO 24", "GPIO 10 (MOSI)", "Ground", "GPIO 9 (MISO)", "GPIO 25", "GPIO 11 (SCLK)",
  "GPIO 8 (CE0)", "Ground", "GPIO 7 (CE1)", "GPIO 0 (ID_SD)", "GPIO 1 (ID_SC)", "GPIO 5", "Ground", "GPIO 6",
  "GPIO 12 (PWM0)", "GPIO 13 (PWM1)", "Ground", "GPIO 19 (PCM_FS)", "GPIO 16", "GPIO 26", "GPIO 20 (PCM_DIN)",
  "Ground", "GPIO 21 (PCM_DOUT)",
]; // prettier-ignore

PI_LABELS.forEach((label, i) => {
  const want = { "3V3": "3V3 power", "5V": "5V power", GND: "Ground" }[PI_HEADER[i] ?? ""] ?? PI_HEADER[i];
  if (label.replace(/^GPIO (\d+).*$/, "GPIO$1") !== want) throw new Error(`PI_LABELS: pin ${i + 1} is ${label}`);
});

for (const w of WIRES) {
  if (PI_HEADER[w.pin - 1] !== `GPIO${w.gpio}`)
    throw new Error(`docs/wiring.md: header pin ${w.pin} is ${PI_HEADER[w.pin - 1] ?? "?"}, not GPIO ${w.gpio}`);
}
