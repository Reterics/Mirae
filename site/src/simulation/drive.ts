export type DriveAction = "forward" | "reverse" | "left" | "right";

export const DRIVE_KEYS: Readonly<Record<string, DriveAction>> = {
  KeyW: "forward",
  ArrowUp: "forward",
  KeyS: "reverse",
  ArrowDown: "reverse",
  KeyA: "left",
  ArrowLeft: "left",
  KeyD: "right",
  ArrowRight: "right",
};

/** Normalized motor commands, not measured speed; positive means driving forward. */
export interface DriveCommand {
  left: number;
  right: number;
}

export const motorState = (command: number): string => (command > 0 ? "Forward" : command < 0 ? "Reverse" : "Idle");

export function driveCommand(actions: ReadonlySet<DriveAction>): DriveCommand {
  const forward = Number(actions.has("forward")) - Number(actions.has("reverse"));
  const turn = Number(actions.has("right")) - Number(actions.has("left"));
  const scale = Math.max(1, Math.abs(forward + turn), Math.abs(forward - turn));
  return { left: (forward + turn) / scale, right: (forward - turn) / scale };
}
