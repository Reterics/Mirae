import stills from "../stills.json";
import model from "./model.json";

/** Steps the 3D model covers; the others show a still (STILL_STEPS) or no figure. */
export const MODEL_STEPS: ReadonlySet<string> = new Set(model.steps.map((s) => s.id));

/** Steps whose scene shows the Raspberry Pi 5 board, so the figure credits its model. */
export const PI_STEPS: ReadonlySet<string> = new Set(
  model.steps.filter((s) => [...s.adds, ...s.after].includes("pi")).map((s) => s.id),
);

/** Steps outside the 3D model that have a prebuilt rendered image instead. */
export const STILL_STEPS: ReadonlySet<string> = new Set(stills);
