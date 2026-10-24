/**
 * Assembly guide content, in build order. Order and counts come from cad/README.md;
 * part names and fasteners from docs/hardware.md, sizes from docs/parts.md.
 * Steps listed in viewer/model.json show in 3D using the prebuilt assembly model.
 *
 * Sides are named by what is there (the USB-C side, the switch side), not left and right, which
 * depend on where you stand.
 */
import type { ReactNode } from "react";

import { Link } from "../components/Link";
import { LINKS } from "../site";
import { textLink } from "../ui";

export type StageId = "prepare" | "base" | "shell" | "close";

export const STAGES: readonly { id: StageId; label: string }[] = [
  { id: "prepare", label: "Prepare" },
  { id: "base", label: "Base" },
  { id: "shell", label: "Upper shell" },
  { id: "close", label: "Close up" },
];

export interface Item {
  name: string;
  qty?: number;
}

export interface Step {
  /** URL hash and render folder. */
  id: string;
  stage: StageId;
  title: string;
  /** What to have on the table for this step. */
  items: readonly Item[];
  instructions: readonly ReactNode[];
  /** Label drawn beside the part in the render. */
  label?: string;
  tip?: ReactNode;
  caution?: ReactNode;
}

const doc = (href: string, text: string) => (
  <Link className={textLink} href={href}>
    {text}
  </Link>
);

export const STEPS: readonly Step[] = [
  // ------------------------------------------------------------------ prepare
  {
    id: "print",
    stage: "prepare",
    title: "Print the five parts",
    items: [
      { name: "chassis.stl (charcoal)", qty: 1 },
      { name: "pi-module.stl (white, PETG recommended)", qty: 1 },
      { name: "top-cover.stl (white)", qty: 1 },
      { name: "faceplate.stl (white or light grey)", qty: 1 },
      { name: "sensor-mount.stl (black)", qty: 1 },
    ],
    instructions: [
      <>Download the STLs from {doc(LINKS.stl, "cad/stl")}. Each part fits a 220 × 220 mm bed in one piece.</>,
      "Print without supports, in PLA or PETG, with a 0.4 mm nozzle and 0.2 mm layers. Use the orientation in the table in cad/README.md: the chassis on its floor, the upper shell on its tray floor, the lid top-down.",
      "The upper shell (pi-module) sits over the warm Pi 5, so print it in PETG if you can.",
      "Print the faceplate in white or light filament: the eye lights glow through a 0.6 mm skin.",
    ],
    tip: "Print a small fit test first and tune the clearance for your printer. Every slide-in fit is designed with 0.35 mm of play per side.",
    caution:
      "The lid prints top-down, so the first layers of its rounded edge overhang a little. Use a brim and print it slowly.",
  },
  {
    id: "solder",
    stage: "prepare",
    title: "Solder the loose headers",
    items: [
      { name: "TB6612FNG-M motor driver, with its two 8-pin headers", qty: 1 },
      { name: "MAX98357-M amplifier, with its 7-pin header and 2-pin screw terminal", qty: 1 },
      { name: "INMP441-M microphone, and thin hook-up wire", qty: 1 },
      { name: "Adafruit VL53L1X (#3967), with its 6-pin header", qty: 1 },
    ],
    instructions: [
      "These four boards come with their pins loose. Solder them before anything goes into the robot; it's much harder once they're inside.",
      "On the motor driver, solder both 8-pin rows so the pins point up when the board lies flat in its pocket. Then the wires plug on from above.",
      "On the amplifier, solder the 7-pin header and the 2-pin screw terminal for the speaker.",
      "On the distance sensor, solder the 6-pin header.",
      "The microphone is glued flat under the lid, where only 3 mm is reserved for it. Its header pins would stick out further, so solder thin wires straight to its pads instead, on the side with the microphone chip.",
    ],
    caution:
      "The heights of these boards with their pins aren't published. Once soldered, measure each one and compare it with the space in docs/parts.md before you go on.",
  },
  {
    id: "pack",
    stage: "prepare",
    title: "Build the battery pack",
    items: [
      { name: "TP-INR18650-35HE cell", qty: 4 },
      { name: "2x18650-HOLDER cell spacer", qty: 4 },
      { name: "NICKEL-STRIP, 100 × 7 × 0.1 mm", qty: 4 },
      { name: "HX-2S-JH20 BMS", qty: 1 },
      { name: "Spot welder", qty: 1 },
    ],
    instructions: [
      "The pack is 2S2P: two pairs of cells in parallel, the pairs in series. Lay it flat as two rows of two cells, end to end.",
      "Clip a spacer onto each of the four cell-end planes, so every spacer holds two side-by-side cells.",
      "Spot-weld the nickel strip to join the cells. Don't solder directly onto the cells.",
      <>
        Connect the BMS to the pack as its wiring diagram shows, then lay it flat on top of the pack. See{" "}
        {doc(LINKS.wiring, "the wiring page")} for the power chain.
      </>,
      "The finished pack should fit in 142 × 41 × 21 mm. Measure it.",
    ],
    caution:
      "Lithium-ion cells can catch fire if they're shorted, punctured or overheated. Only build the pack if you've spot-welded cells before, cover the terminals while you work, and never leave it charging unattended.",
  },
  {
    id: "voltages",
    stage: "prepare",
    title: "Set both converter outputs",
    items: [
      { name: "SZ-08CV step-up/down converter", qty: 1 },
      { name: "XL6009-UD step-up/step-down converter", qty: 1 },
      { name: "Multimeter", qty: 1 },
    ],
    instructions: [
      "Power each converter from the pack (through the BMS) or a bench supply within its input range: 5–30 V for both the SZ-08CV and the XL6009-UD.",
      "With nothing connected to the output, adjust the SZ-08CV to 5.1 V. This rail feeds the Pi 5, the amplifier and the logic.",
      "Adjust the XL6009-UD to 12.0 V. This rail feeds the motors through the driver.",
      "Disconnect the power again.",
    ],
    caution:
      "Set the outputs before you connect any load. A converter left at the wrong voltage can damage the Pi or the motors the moment it's connected.",
  },
  {
    id: "inserts",
    stage: "prepare",
    title: "Press in the heat-set inserts",
    label: "Heat-set inserts",
    items: [
      { name: "Printed chassis", qty: 1 },
      { name: "M3-INSERT-6 heat-set insert, M3 × 4.6 × 6.0", qty: 8 },
      { name: "M4-INSERT-6X6 heat-set insert, M4 × 6.0 × 6.0", qty: 3 },
      { name: "Soldering iron with an insert tip", qty: 1 },
    ],
    instructions: [
      "Four M3 inserts go into the tops of the four tall posts in the chassis. The upper shell screws down onto these.",
      "Four M3 inserts go into the four short standoffs in the rear bay, where the SZ-08CV will sit.",
      "Turn the chassis over. The three M4 inserts go into the three holes around the large round opening near the front of the underside, for the ball caster.",
      "Press each insert in straight with the hot iron until it's flush, then hold it level for a moment while the plastic sets.",
    ],
    tip: "The holes are Ø4.2 mm for M3 and Ø5.6 mm for M4. If an insert goes in crooked, reheat it and straighten it before the plastic cools.",
  },

  // ------------------------------------------------------------------ base
  {
    id: "wheels",
    stage: "base",
    title: "Press the wheels onto the motors",
    label: "N20-3PI-WHL wheel",
    items: [
      { name: "N20E-12-100 geared motor with encoder", qty: 2 },
      { name: "N20-3PI-WHL wheel, 42 mm", qty: 2 },
    ],
    instructions: [
      "Each motor has a 3 mm D-shaped shaft at the gearbox end. Line up the flat on the shaft with the flat in the wheel's hub.",
      "Press the wheel straight on until it's firm. Support the motor's gearbox, not the encoder board at the other end.",
    ],
  },
  {
    id: "motors",
    stage: "base",
    title: "Seat the motors and tie them down",
    label: "Motor and wheel",
    items: [
      { name: "Motor and wheel unit (from the last step)", qty: 2 },
      { name: "CV 100/2,5/B cable tie, 2.5 × 100 mm", qty: 4 },
    ],
    instructions: [
      "Each motor plate inside the chassis has an open-topped U slot. Lower a motor in with its wheel outside the plate and the encoder pointing in toward the middle.",
      "The round gearbox boss drops into the U slot and carries the load. The motor body sits between two low rails on the floor, and the wheel hangs in its well.",
      "Thread a cable tie down through one floor slot beside the motor and back up through the slot on the other side, over the motor. Each motor gets two ties, one near the gearbox and one near the encoder.",
      "Pull the ties snug and trim the tails.",
    ],
    tip: "Leave the encoder cables free above the motors; they plug in when you wire the base.",
  },
  {
    id: "driver",
    stage: "base",
    title: "Drop the motor driver into its pocket",
    label: "TB6612FNG driver",
    items: [{ name: "TB6612FNG-M motor driver, headers soldered", qty: 1 }],
    instructions: [
      "Find the small pocket on the base floor, between the two motors.",
      "Hold the driver with its pin headers pointing up.",
      "Lower it straight down until the board rests on the floor of the pocket. The side rails and the back stop hold it; no screws.",
    ],
    tip: "The pocket is sized for the board with 0.35 mm of play on each side. If it's tight, check for stringing on the rails before you push.",
  },
  {
    id: "battery",
    stage: "base",
    title: "Strap the battery pack into its cradle",
    label: "2S2P pack with BMS",
    items: [
      { name: "Battery pack with BMS (from Prepare)", qty: 1 },
      { name: "VELCRO-BK hook-and-loop strap, 20 × 300 mm", qty: 2 },
    ],
    instructions: [
      "Thread both straps through the pairs of floor slots on either side of the cradle, so each one runs under the floor.",
      "Lay the pack flat in the low cradle in front of the motors, with the BMS on top.",
      "Wrap each strap over the pack and close it firmly. The pack must not move when you shake the chassis.",
    ],
    tip: "The long sides of the cradle are open in the middle, so the pack's wires can leave along it.",
    caution: "The pack is built in and isn't meant to come out. Keep its output disconnected until the wiring step.",
  },
  {
    id: "sz08cv",
    stage: "base",
    title: "Screw the 5.1 V converter to its standoffs",
    label: "SZ-08CV",
    items: [
      { name: "SZ-08CV, already set to 5.1 V", qty: 1 },
      { name: "M 3 x 6 DBKNY socket head screw, M3 × 6", qty: 4 },
    ],
    instructions: [
      "The SZ-08CV sits in the rear bay on the four short standoffs with inserts, over the floor vents.",
      "Line up its four mounting holes (45 × 37 mm apart) with the standoffs.",
      "Screw it down with the four M3 × 6 screws. Snug is enough.",
    ],
  },
  {
    id: "motor-supply",
    stage: "base",
    title: "Place the motor supply and the capacitor",
    label: "XL6009-UD",
    items: [
      { name: "XL6009-UD, already set to 12.0 V", qty: 1 },
      { name: "M 2,5 x 6 DF screw, M2.5 × 6", qty: 2 },
      { name: "1000 µF / 16 V low-ESR capacitor", qty: 1 },
    ],
    instructions: [
      "Find the two short standoffs in the front corner on the switch side, between the battery and the sensor slot.",
      "Set the XL6009-UD on them, component side up, with its IN pads toward the side wall and its OUT pads toward the middle. Its two corner holes sit over the standoffs.",
      "Drive an M2.5 × 6 screw through each hole into its standoff. The plastic cuts its own thread, so stop as soon as the board is held.",
      "Lay the capacitor on its side, in front of the motor on the switch side, between it and the battery. Its leads get soldered across the driver's motor supply (VM and GND) in the wiring step, so keep them close to the driver.",
    ],
    tip: "The capacitor has no printed holder yet. Once the wiring holds it in place, check it can't touch the wheels or the motor cans.",
  },
  {
    id: "charger",
    stage: "base",
    title: "Set the USB-C charger on its rails",
    label: "USBC-2S-LI-BOOST",
    items: [{ name: "USBC-2S-LI-BOOST charger", qty: 1 }],
    instructions: [
      "At the rear wall on the USB-C side are two low rails between side guides, with a stop at the front.",
      "Lower the charger between the guides with its USB-C port facing the rear wall.",
      "Slide it back until the port sits in the slot in the wall. From outside you should see the whole port opening.",
    ],
    caution:
      "The size of this board isn't published. The rails are designed for 35 × 22 mm, a provisional value. Measure yours before printing; if it differs, the rails have to change.",
  },
  {
    id: "switch",
    stage: "base",
    title: "Fit the power switch",
    label: "SL 19123 switch",
    items: [{ name: "SL 19123 slide switch", qty: 1 }],
    instructions: [
      "The switch goes into a small pocket inside the rear wall, on the side opposite the USB-C port.",
      "Hold it with its legs pointing into the robot and its slider toward the wall.",
      "Slide it into the pocket until the slider pokes out through the slot in the rear wall. It stands about 2 mm proud of a shallow recess.",
      "Set it to off.",
    ],
    tip: "The switch only cuts the robot's power. Charging is wired straight to the BMS, so it charges with the switch off.",
  },
  {
    id: "sensors",
    stage: "base",
    title: "Fit the camera and distance sensor to the sensor mount",
    items: [
      { name: "Printed sensor mount", qty: 1 },
      { name: "Raspberry Pi Camera Module 3 NoIR, with its ribbon cable", qty: 1 },
      { name: "M 2 x 6 DF screw, M2 × 6 stainless (camera)", qty: 4 },
      { name: "Adafruit VL53L1X (#3967), header soldered", qty: 1 },
      { name: "M 2,5 x 6 DF screw, M2.5 × 6 (VL53L1X)", qty: 4 },
    ],
    instructions: [
      "Set the camera board on its four standoffs at the back of the mount, with the lens through the square window, and fix it with the four M2 screws.",
      "Set the VL53L1X on the four short standoffs with its sensor facing the mount, so it looks through its window. Its two STEMMA QT sockets face the mount too.",
      "Fix it with the four M2.5 screws. They cut their own thread in the standoffs, so drive them gently and stop when the board is held.",
    ],
    caution:
      "Check the camera's hole pattern against your board before driving the screws; it hasn't been confirmed on a real part.",
  },
  {
    id: "sensor-mount",
    stage: "base",
    title: "Slide the sensor mount into the front",
    label: "Sensor mount",
    items: [{ name: "Sensor mount with camera and distance sensor", qty: 1 }],
    instructions: [
      "The front wall of the chassis has a slot that's open at the top.",
      "Hold the mount with the camera lens and the sensor window facing forward, and slide it straight down into the slot.",
      "Look from the front: the lens and the sensor should be centred in their openings.",
    ],
    tip: "Let the camera ribbon hang inside for now. It goes up to the Pi later, through its own slot in the upper shell.",
  },
  {
    id: "caster",
    stage: "base",
    title: "Screw on the ball caster",
    label: "Ball caster",
    items: [
      { name: "GG-KUB-30-B ball transfer unit, Ø30 ball", qty: 1 },
      { name: "Printed caster spacer, 1.7 mm", qty: 1 },
      { name: "M4 screw (length to be confirmed)", qty: 3 },
    ],
    instructions: [
      "Turn the chassis upside down on a soft cloth.",
      "Lay the spacer over the round opening near the front, its three holes over the M4 inserts.",
      "Set the caster on it, ball facing up, its cup through the opening and its three holes over the inserts.",
      "Screw it on with the three M4 screws.",
    ],
    tip: "The screw length depends on the caster flange's sheet thickness, which still has to be measured: the screws pass through the flange and the 1.7 mm spacer into the 6 mm inserts.",
  },
  {
    id: "wire-base",
    stage: "base",
    title: "Wire the base",
    items: [
      { name: "Wire and connectors to suit the modules", qty: 1 },
      { name: "Soldering iron and multimeter", qty: 1 },
    ],
    instructions: [
      <>
        Follow {doc(LINKS.wiring, "the wiring page")}. Power goes: pack → BMS → power switch → the SZ-08CV and XL6009-UD
        branches. The USB-C charger connects straight to the BMS.
      </>,
      "Wire the XL6009-UD's OUT+ to the driver's VM and its OUT− to the driver's GND, and solder the capacitor across VM and GND close to the driver. The driver's GND never goes to a Pi GND pin.",
      "Plug in both encoder cables and wire the motors to the driver outputs.",
      "Leave the signal wires that go to the Pi long enough to reach up into the upper shell.",
      "With the switch on, check both rails with a multimeter (5.1 V and 12.0 V), then switch off again.",
    ],
    caution:
      "The pin map hasn't been verified on a robot yet. Check every connection against each module's pinout before you power up.",
  },

  // ------------------------------------------------------------------ upper shell
  {
    id: "ai-hat",
    stage: "shell",
    title: "Optional: fit the AI HAT+ 2",
    label: "AI HAT+ 2 (optional)",
    items: [
      { name: "Printed upper shell (pi-module)", qty: 1 },
      { name: "Raspberry Pi AI HAT+ 2, with its heatsink", qty: 1 },
      { name: "PCIe ribbon cable, long enough for a loop of about 43 mm", qty: 1 },
      { name: "Wires with a female header socket on one end (5 V and GND)", qty: 2 },
    ],
    instructions: [
      "Skip this step if you aren't using the AI HAT+ 2. The space under the Pi is there either way, and the next step works the same without it.",
      "Fit the heatsink to the HAT first: its two spring pins push through the holes beside the chip.",
      "The tray floor has four short standoffs, 58 × 49 mm apart. The HAT shares this hole pattern with the Pi 5, but it goes under the Pi here, not on its GPIO header.",
      "Set the HAT on the standoffs, with its 40-pin side toward the back and the notch with the ribbon connector toward the speaker side.",
      "Plug the ribbon cable into the HAT's connector and leave its other end free. It loops up to the Pi in the next step.",
      "Push one wire's socket onto a 5 V pin of the HAT's 40-pin header (pin 2 or 4) and the other onto a GND pin (pin 6). Their other ends go to the SZ-08CV's Vout+ and Vout− terminals in the base.",
    ],
    tip: "The 15 mm spacers in the next step screw through the HAT's mounting holes, so they also hold it down.",
    caution:
      "Only power and ground are wired, so the Pi can't read the HAT's ID chip. If the HAT doesn't show up, enable the PCIe connector yourself with dtparam=pciex1 in /boot/firmware/config.txt. This layout comes from the CAD model and hasn't been tested on hardware.",
  },
  {
    id: "pi",
    stage: "shell",
    title: "Mount the Pi 5 in the upper shell",
    label: "Raspberry Pi 5",
    items: [
      { name: "Raspberry Pi 5, with the cooler or case of your choice", qty: 1 },
      { name: "RI M2,5x15 BB spacer, M2.5 × 15 mm, female–female", qty: 4 },
      { name: "M 2,5 x 10 DF screw, M2.5 × 10 (from under the tray)", qty: 4 },
      { name: "M2.5 screws, to suit your cooler or case (into the spacers)", qty: 4 },
    ],
    instructions: [
      "From underneath the tray, push an M2.5 × 10 screw up through each of the four standoffs (and through the HAT, if you fitted it), and screw a 15 mm spacer onto it from above.",
      "Set the Pi on the spacers, with its mounting holes over them, and fix it with the screws for your cooler or case.",
      "With the AI HAT+ 2: loop its ribbon cable up past the Pi's short edge on the speaker side and plug it into the Pi's PCIe connector there, without folding it. Its two power wires don't go on the Pi's header: both 5 V pins there already take the SZ-08CV feed. They go down to the SZ-08CV's terminals with the other wires.",
    ],
    caution:
      "The Pi 5 needs cooling. Any cooler or passive case works if it fits within 91 × 65 × 34 mm on top of the spacers, the space the enclosure reserves and checks. With a closed case, check that its ribbon slot lines up with the Pi's PCIe connector.",
  },
  {
    id: "speaker",
    stage: "shell",
    title: "Slide in the speaker",
    label: "3525 speaker",
    items: [{ name: "3525-SPKR-4R-3W speaker, 35 × 25 mm", qty: 1 }],
    instructions: [
      "Find the oval grille in one side wall of the upper shell. Just inside it is a slot between two ribs.",
      "Hold the speaker with its large face toward the grille and slide it down into the slot.",
      "Peel its adhesive pad and press it to the wall if you want it held more firmly.",
    ],
  },
  {
    id: "amp",
    stage: "shell",
    title: "Place the amplifier",
    label: "MAX98357 amplifier",
    items: [{ name: "MAX98357-M amplifier, header and terminal soldered", qty: 1 }],
    instructions: [
      "The amplifier sits flat on the tray near the back, on the same side as the speaker.",
      "Screw the speaker's two wires into the amplifier's terminal.",
      "Secure the board so it can't slide, for example with a piece of double-sided foam tape.",
    ],
    tip: "There's no printed holder for the amplifier yet. Its height with the screw terminal isn't published, so measure it.",
  },
  {
    id: "cables",
    stage: "shell",
    title: "Bring the cables up through the tray",
    items: [{ name: "Chassis (base) and upper shell, side by side", qty: 1 }],
    instructions: [
      "Hold the upper shell above the base.",
      "Pass the camera ribbon up through the narrow slot in the tray floor and connect it to the Pi's camera port.",
      "Pass the power and signal wires from the base up through the two cable slots on either side, and connect them to the Pi as the wiring page shows.",
    ],
    tip: "Leave a little slack in every cable, so the shell can sit down without pulling on them.",
  },

  // ------------------------------------------------------------------ close up
  {
    id: "join",
    stage: "close",
    title: "Screw the upper shell to the base",
    label: "Upper shell",
    items: [
      { name: "M 3 x 8 DBKNY socket head screw, M3 × 8", qty: 4 },
      { name: "Hex key or driver, long enough to reach the tray floor", qty: 1 },
    ],
    instructions: [
      "Lower the upper shell onto the base, folding the cables in so none of them gets pinched at the seam.",
      "Inside the shell, four holes in the tray floor line up with the inserts in the base posts.",
      "Drive an M3 × 8 screw down through each hole into its insert, from above. The path to each screw is kept clear of the Pi and the speaker.",
    ],
    tip: "To reach the base electronics later, undo these four screws and lift the shell.",
  },
  {
    id: "faceplate",
    stage: "close",
    title: "Slide in the faceplate",
    label: "Faceplate",
    items: [{ name: "Printed faceplate", qty: 1 }],
    instructions: [
      "The front of the upper shell has a slot that's open at the top, with a rail frame behind it.",
      "Hold the faceplate with its flange at the back, and slide it straight down until it rests at the bottom of the slot.",
      "The lid holds it down once it's on. To take the faceplate out, take the lid off and pull it up.",
    ],
    caution:
      "The faceplate has two blind holes for the eye lights and one for the status light, but the LEDs aren't chosen or in the parts list yet. You can leave them out for now.",
  },
  {
    id: "mic",
    stage: "close",
    title: "Glue the microphone under the lid",
    label: "INMP441 microphone",
    items: [
      { name: "Printed lid (top-cover)", qty: 1 },
      { name: "INMP441-M microphone, wires soldered", qty: 1 },
    ],
    instructions: [
      "Turn the lid over and find the small mic port near its front.",
      "The microphone's sound hole is on the underside of its board. Put that side against the lid, with the hole right over the port.",
      "Glue the board's edge in place, keeping glue well away from the sound hole and the port.",
      "Run its wires to the Pi as the wiring page shows, with enough slack to lift the lid off.",
    ],
  },
  {
    id: "magnets",
    stage: "close",
    title: "Glue in the four lid magnets",
    items: [
      { name: "Ø5 × 2 mm N38 neodymium magnet (orodian.hu V5-2-N38)", qty: 4 },
      { name: "Glue for plastic and metal", qty: 1 },
    ],
    instructions: [
      "Two magnets go into the pockets on top of the two front corner columns in the upper shell.",
      "Two go into the pockets in the two bosses under the front of the lid.",
      "Before gluing, stack each lid magnet onto its column magnet: they must attract. Mark the face of each lid magnet that points down, so you glue it the right way round.",
      "Glue all four flush and let the glue set before you fit the lid.",
    ],
    caution: "Neodymium magnets snap together hard and can pinch skin or chip. Keep them away from cards and phones.",
  },
  {
    id: "lid",
    stage: "close",
    title: "Put the lid on",
    label: "Lid",
    items: [{ name: "Lid, with microphone and magnets", qty: 1 }],
    instructions: [
      "Hold the lid with its front raised.",
      "Lower the back first, so the two hidden hooks under the rear edge slip into the keepers on the rear wall.",
      "Lower the front. The skirt under the lid finds its place inside the walls and the magnets close.",
      "To take it off, lift the front, swing it up about its back edge, then lift it away.",
    ],
  },
];

export const stepIndex = (id: string): number => STEPS.findIndex((s) => s.id === id);
