import { type DriveCommand, motorState } from "./drive";
import { cx } from "../lib";

/** The actual assembly GLB is rendered below this overlay by SimulationStage. */
export function ComponentHud({
  drive,
  open,
  onToggle,
}: {
  drive: DriveCommand;
  open: boolean;
  onToggle: (open: boolean) => void;
}) {
  return (
    <details
      className="component-hud"
      aria-label="Top-view component activity"
      open={open}
      onToggle={(event) => {
        onToggle(event.currentTarget.open);
      }}
    >
      <summary className="hud-heading">
        <span>COMPONENTS</span>
        <span>TOP ↑</span>
      </summary>
      <div className="hud-render-area hud-model-overlay" aria-hidden="true">
        <canvas />
        <span className={cx("hud-rotation hud-rotation-left", drive.left !== 0 && "is-active")}>
          {drive.left > 0 ? "↶" : "↷"}
        </span>
        <span className={cx("hud-rotation hud-rotation-right", drive.right !== 0 && "is-active")}>
          {drive.right > 0 ? "↷" : "↶"}
        </span>
      </div>
      <div className="hud-readings">
        <span>
          L <strong>{motorState(drive.left)}</strong>
        </span>
        <span>
          R <strong>{motorState(drive.right)}</strong>
        </span>
      </div>
      <p>Actual CAD · upper shell hidden</p>
    </details>
  );
}
