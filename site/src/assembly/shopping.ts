import hardware from "../../../docs/hardware.md?raw";
import { LINKS, REPO } from "../site";

export interface ShoppingPart {
  name: string;
  qty: number;
  description: string;
  href: string;
  source: string;
}

/** Read the canonical bill of materials, so quantities stay in sync with the hardware guide. */
const hestore: ShoppingPart[] = hardware.split("\n").flatMap((line) => {
  const cells = line.split("|").map((cell) => cell.trim());
  const [, id, name, description, , quantity] = cells;
  if (!id || !/^\d{3}\.\d{3}\.\d{2}$/.test(id) || !name || !description || !quantity) return [];
  return [
    {
      name,
      qty: Number(quantity),
      description,
      href: `https://www.hestore.hu/prod_${id.replaceAll(".", "")}.html`,
      source: `HESTORE · ${id}`,
    },
  ];
});

const guidance = LINKS.partsList;

export const SHOPPING_GROUPS: readonly { title: string; parts: readonly ShoppingPart[] }[] = [
  {
    title: "HESTORE parts",
    parts: hestore,
  },
  {
    title: "Buy separately",
    parts: [
      {
        name: "Raspberry Pi 5",
        qty: 1,
        description: "Main computer; choose your memory capacity.",
        href: "https://www.raspberrypi.com/products/raspberry-pi-5/",
        source: "Raspberry Pi",
      },
      {
        name: "Pi 5 cooler or passive case",
        qty: 1,
        description: "Must fit within 91 × 65 × 34 mm. JOY-IT RB-AlucaseP5-09 is one example.",
        href: "https://joy-it.net/en/products/RB-AlucaseP5-09",
        source: "JOY-IT",
      },
      {
        name: "Adafruit VL53L1X · #3967",
        qty: 1,
        description: "Distance sensor; the mount fits this board’s four-hole pattern.",
        href: "https://www.adafruit.com/product/3967",
        source: "Adafruit",
      },
      {
        name: "GG-KUB-30-B ball caster",
        qty: 1,
        description: "Flanged ball transfer unit with a Ø30 mm steel ball.",
        href: "https://kerekaruhaz.hu/spd/308640/GG-KUB-30-B-peremes-sullyesztheto-rogzito-furatos",
        source: "kerekaruhaz.hu",
      },
      {
        name: "V5-2-N38 neodymium magnets",
        qty: 4,
        description: "Ø5 × 2 mm, N38; two pairs for the lid.",
        href: "https://orodian.hu/termek/neodimium-hengermagnes-5x2-mm-n38",
        source: "orodian.hu",
      },
      {
        name: "M4 caster screws",
        qty: 3,
        description: "Length TBD: measure the caster flange before buying.",
        href: guidance,
        source: "Sizing guidance",
      },
      {
        name: "M2.5 Pi case screws",
        qty: 4,
        description: "Choose the length your cooler or case needs to fix it to the spacers.",
        href: guidance,
        source: "Sizing guidance",
      },
    ],
  },
  {
    title: "Optional AI hardware",
    parts: [
      {
        name: "Raspberry Pi AI HAT+ 2, 40 TOPS",
        qty: 1,
        description: "Include its heatsink. Mounted under the Pi, rather than on its GPIO header.",
        href: guidance,
        source: "Hardware guide",
      },
      {
        name: "PCIe FFC for the AI HAT",
        qty: 1,
        description:
          "Not chosen yet: allow a 180° loop of about 43 mm, with the same contact orientation as the supplied cable.",
        href: guidance,
        source: "Cable requirements",
      },
      {
        name: "Female-ended jumper wires",
        qty: 2,
        description: "5 V and GND for the optional AI HAT.",
        href: guidance,
        source: "Hardware guide",
      },
    ],
  },
  {
    title: "Print the enclosure",
    parts: ["chassis", "pi-module", "top-cover", "faceplate", "sensor-mount", "caster-spacer"].map((name) => ({
      name: `${name}.stl`,
      qty: 1,
      description:
        name === "pi-module"
          ? "PETG recommended for the warm Pi enclosure."
          : name === "caster-spacer"
            ? "1.7 mm spacer under the caster flange."
            : "See the CAD guide for material and print orientation.",
      href: `${REPO}/blob/main/cad/stl/${name}.stl`,
      source: "STL file",
    })),
  },
];

export const SHOPPING_TOOLS = [
  "Spot welder for the battery pack",
  "Soldering iron, solder and an insert tip",
  "Multimeter",
  "Hex key or screwdriver long enough to reach the tray floor",
  "Thin hook-up wire and connectors to suit the modules",
  "Glue for plastic and metal",
];
