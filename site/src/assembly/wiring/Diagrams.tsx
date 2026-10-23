import { BaseWiringDiagram } from "./BaseWiringDiagram";
import { type DiagramProps, WiringFigure } from "./WiringFigure";

/** The base wiring uses the same fitted / full-size presentation as the Pi wiring step. */
export function PowerChain({ watch }: DiagramProps) {
  return <WiringFigure Diagram={BaseWiringDiagram} label="Base wiring diagram" watch={watch} />;
}
