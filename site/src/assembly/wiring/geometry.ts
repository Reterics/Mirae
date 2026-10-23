/** Schematic grid: pin stub length and pin pitch, and the part shape the symbols draw. */
export const PIN = 30; // pin stub length
export const ROW = 20; // pin pitch

export type Side = "L" | "R";
export interface PinDef {
  name: string;
  side: Side;
  /** Row from the top of the body, 0-based. */
  row: number;
  number?: string;
}
export interface PartDef {
  ref: string;
  value: string;
  /** Top-left corner of the body. */
  x: number;
  y: number;
  w: number;
  rows: number;
  pins: readonly PinDef[];
}

export const bodyH = (p: PartDef): number => (p.rows + 1) * ROW;
