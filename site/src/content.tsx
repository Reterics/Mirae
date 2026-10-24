/** Page copy and data. Sections render these lists; edit text here, not in the components. */
import type { ReactNode } from "react";

import { LINKS } from "./site";

export interface NavItem {
  path: string;
  label: string;
}

export const NAV: readonly NavItem[] = [
  { path: "/", label: "Home" },
  { path: "/assembly", label: "Assembly" },
  { path: "/simulation", label: "Simulation" },
];

export const FACTS: readonly { value: string; detail: string }[] = [
  { value: "190 × 210 × 145 mm", detail: "about 1.5 kg" },
  { value: "Raspberry Pi 5", detail: "vision, speech, AI" },
  { value: "5 printed parts", detail: "no supports needed" },
  { value: "Local-first", detail: "moves safely offline" },
];

export type Swatch = "cam" | "tof" | "dot" | "route" | "stop";

export interface Scene {
  num: string;
  title: string;
  body: string;
  legend: readonly { swatch: Swatch; text: string }[];
  image: { file: string; width: number; height: number; alt: string };
  variant?: "flip" | "map";
}

export const SCENES: readonly Scene[] = [
  {
    num: "01 · Sees",
    title: "It knows what's in front of it.",
    body: "Person and object detection and tracking with OpenCV, from a low, forward-looking camera. A time-of-flight sensor measures the distance to whatever is ahead.",
    legend: [
      { swatch: "cam", text: "Camera Module 3 NoIR · 66° × 41° field of view" },
      { swatch: "tof", text: "VL53L1X time-of-flight · 27° cone" },
    ],
    image: {
      file: "scene-sees.webp",
      width: 2400,
      height: 1350,
      alt: "Mirae on the living-room floor facing a coffee table; a warm wedge shows its camera's field of view and a narrower cool cone its distance sensor",
    },
  },
  {
    num: "02 · Hears and speaks",
    title: "Talk to it like a person.",
    body: "Whisper speech recognition and Piper text-to-speech over I2S audio. Recognition can run on the Pi, on another machine on your network or through a remote API.",
    legend: [
      { swatch: "dot", text: "INMP441 I2S microphone under the lid" },
      { swatch: "dot", text: "4 Ω / 3 W speaker on a MAX98357 amplifier" },
    ],
    image: {
      file: "scene-hears.webp",
      width: 2400,
      height: 1350,
      alt: "Mirae in a sunlit living room with faint sound rings leaving the speaker grille on its side",
    },
    variant: "flip",
  },
  {
    num: "03 · Moves safely",
    title: "It stops before it bumps.",
    body: "Differential drive with wheel encoders. A safety governor sits between every command and the motors: when the distance sensor sees an obstacle, Mirae stops, turns and looks for open floor.",
    legend: [
      { swatch: "route", text: "Route" },
      { swatch: "stop", text: "Stop zone, measured by the ToF sensor" },
      { swatch: "dot", text: "2× N20 gearmotors with encoders · TB6612FNG" },
    ],
    image: {
      file: "scene-moves.webp",
      width: 2000,
      height: 2000,
      alt: "Top-down view of the living room: Mirae's route leads toward the coffee table, stops in a glowing zone before a table leg, then turns into open floor",
    },
    variant: "map",
  },
];

export const PRINCIPLES: readonly { title: string; body: ReactNode }[] = [
  {
    title: "Thinks",
    body: "A provider-independent AI layer (Ollama, local models or remote APIs) that emits high-level intents, never raw motor commands.",
  },
  { title: "Works offline", body: "Core movement and safety never depend on the network or the AI backend." },
  {
    title: "Controllable",
    body: (
      <>
        A local FastAPI service for control, telemetry and debugging, with interactive docs at{" "}
        <code className="font-mono text-[0.9em] leading-[normal] font-medium text-ink-2">/docs</code>.
      </>
    ),
  },
];

/** Cutaway labels; `anchor` keys into the prebuilt xray-anchors.json. */
export const XRAY_LABELS: readonly { anchor: string; side: "l" | "r"; text: string }[] = [
  { anchor: "pi", side: "r", text: "Raspberry Pi 5" },
  { anchor: "speaker", side: "l", text: "Speaker" },
  { anchor: "battery", side: "r", text: "4× 18650 Li-ion" },
  { anchor: "drive", side: "l", text: "N20 drive" },
  { anchor: "camera", side: "r", text: "Camera + ToF" },
];

export const SPEC: readonly { term: string; detail: string }[] = [
  {
    term: "Compute",
    detail:
      "Raspberry Pi 5 with a passive cooling case (shown without it), and room under it for an optional AI HAT+ 2",
  },
  { term: "Vision", detail: "Camera Module 3 NoIR (Sony IMX708, 12 MP)" },
  { term: "Distance", detail: "VL53L1X time-of-flight sensor" },
  { term: "Drive", detail: "2× N20 geared motors with encoders, 42 mm wheels, TB6612FNG driver, ball caster" },
  { term: "Audio", detail: "INMP441 I2S microphone, MAX98357 amplifier, 4 Ω / 3 W speaker" },
  {
    term: "Power",
    detail: "4× 18650 Li-ion (2S2P, 6.8 Ah) with BMS, 5.1 V supply for the Pi, 12 V motor supply, USB-C charging",
  },
];

/** Turntable chapters; `label` also names the progress tick. */
export const CHAPTERS: readonly { label: string; title: string; body: string }[] = [
  {
    label: "Face",
    title: "Two points of light.",
    body: 'Diffused LED eyes and an off-axis status light sit on a removable front panel that is already shaped for a 2–3.5" display.',
  },
  {
    label: "Voice",
    title: "A grille, not a face.",
    body: "The speaker sits behind an oval grille on the side, and the microphone listens through a port in the lid.",
  },
  {
    label: "Shape",
    title: "Soft radii, sloped back.",
    body: "A warm-white upper shell over a wider charcoal base. The walls lean in as they rise and the top falls toward the rear.",
  },
  {
    label: "Stance",
    title: "A wide, stable triangle.",
    body: "Two N20 wheels sit 30 mm behind centre and a ball caster sits far forward: a 139 mm track and 97 mm wheelbase.",
  },
];

export type Filament = "white" | "charcoal" | "black";

export const PARTS: readonly { name: string; size: string; colour: Filament }[] = [
  { name: "chassis", size: "187 × 210 × 38", colour: "charcoal" },
  { name: "pi-module", size: "179 × 199 × 82", colour: "white" },
  { name: "top-cover", size: "163 × 173 × 17", colour: "white" },
  { name: "faceplate", size: "108 × 75 × 4.4", colour: "white" },
  { name: "sensor-mount", size: "104 × 34 × 9.7", colour: "black" },
];

export interface PipelineStep {
  name: string;
  detail: string;
  variant?: "ai" | "safe";
}

export const PIPELINE: readonly PipelineStep[] = [
  { name: "Sensors", detail: "Camera · mic · ToF" },
  { name: "Vision / Speech", detail: "OpenCV · Whisper" },
  { name: "AI (LLM)", detail: "emits intents", variant: "ai" },
  { name: "Behavior engine", detail: "deterministic" },
  { name: "Safety", detail: "governor", variant: "safe" },
  { name: "Motors", detail: "TB6612FNG · N20" },
];

export const VOCABULARY: readonly string[] = [
  "stop",
  "move",
  "turn",
  "approach_person",
  "follow_person",
  "explore",
  "say",
  "sleep",
];

export const ROADMAP: readonly { version: string; title: string; body: string; current?: boolean }[] = [
  { version: "v0.1", title: "Movement", body: "GPIO, motor driver, basic REST API", current: true },
  { version: "v0.2", title: "Sensors", body: "ToF, obstacle stop, encoders, odometry" },
  { version: "v0.3", title: "Vision", body: "Camera streaming, person detection and tracking" },
  { version: "v0.4", title: "Voice", body: "Microphone, speaker, Whisper, TTS" },
  { version: "v0.5", title: "AI", body: "LLM abstraction, Ollama, behavior engine" },
  { version: "v0.6", title: "Autonomy", body: "Exploration, following, personality states" },
  { version: "v1.0", title: "Complete robot", body: "Final enclosure, battery, reproducible build" },
];

export const DOC_LINKS: readonly { label: string; href: string }[] = [
  { label: "Architecture", href: LINKS.architecture },
  { label: "Hardware", href: LINKS.hardware },
  { label: "Wiring", href: LINKS.wiring },
  { label: "CAD", href: LINKS.cad },
  { label: "Roadmap", href: LINKS.roadmap },
];

/** Terminal text: one array per line; a segment is plain text or a [token, text] pair. */
export type Token = "comment" | "key" | "value" | "accent" | "error";
export type TermLine = readonly (string | readonly [Token, string])[];

export const INTENT_EXAMPLE: readonly TermLine[] = [
  [["comment", "# accepted: in the vocabulary, speed within its bound"]],
  [
    "{ ",
    ["key", '"action"'],
    ": ",
    ["value", '"approach_person"'],
    ", ",
    ["key", '"speed"'],
    ": ",
    ["accent", "0.25"],
    " }",
  ],
  [],
  [["comment", "# rejected: not an intent, so it never reaches the motors"]],
  [
    "{ ",
    ["key", '"action"'],
    ": ",
    ["error", '"set_motor_pwm"'],
    ", ",
    ["key", '"left"'],
    ": ",
    ["accent", "255"],
    " }",
  ],
];

export const QUICK_START: readonly TermLine[] = [
  [["accent", "$"], " uv sync"],
  [],
  [["accent", "$"], " uv run mirae run"],
  [["comment", "INFO mirae.robot: starting Mirae (sim backend)"]],
  [["comment", "INFO:     Application startup complete."]],
  [["comment", "INFO:     Uvicorn running on http://127.0.0.1:8000"]],
  [],
  [["accent", "$"], " uv run pytest"],
  [
    ["value", "33 passed"],
    ["comment", " in 0.56s"],
  ],
];
