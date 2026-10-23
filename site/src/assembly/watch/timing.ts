/** How long each step plays in watch mode, at 1×. */
import { STEPS, type Step } from "../steps";
import { MODEL_STEPS } from "../viewer/model";

/** The camera glides in from the last step, then the part slides home. */
export const GLIDE_MS = 1000;
export const INSERT_MS = 2200;
const HOLD_MS = 2800; // seated, so the caption can be read
const STILL_MS = 5000; // a rendered image
const DIAGRAM_MS = 8000; // a wiring diagram has more to take in

export function stepMs(step: Step, diagrams: ReadonlySet<string>): number {
  if (MODEL_STEPS.has(step.id)) return GLIDE_MS + INSERT_MS + HOLD_MS;
  return diagrams.has(step.id) ? DIAGRAM_MS : STILL_MS;
}

/** Start of each step and the total, in ms at 1×. */
export function timeline(diagrams: ReadonlySet<string>): { starts: number[]; total: number } {
  const starts: number[] = [];
  let at = 0;
  for (const step of STEPS) {
    starts.push(at);
    at += stepMs(step, diagrams);
  }
  return { starts, total: at };
}

export const SPEEDS = [1, 1.5, 2] as const;
export type Speed = (typeof SPEEDS)[number];

export const clock = (ms: number): string => {
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
