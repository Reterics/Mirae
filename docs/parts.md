# Parts reference

What each bought part really measures, compared with the space the enclosure reserves for it (see the [enclosure guide](../cad/README.md)). Checked against the HESTORE product pages and the documents they link to, October 2026.

Source tags:

- **H**: HESTORE product page
- **H-doc**: a document or drawing linked from that page
- **other**: another vendor's listing
- **measure**: no published value, so measure the part you received

Status:

- ✅ the CAD matches
- ⚠️ close, or not fully known
- ❌ mismatch: the enclosure has to change

The tables link directly to vendor product pages, drawings and datasheets. Check these sources and measure the parts you receive before assembly.

## Drive

| Part | Real size (mm) | Source | CAD reserves | Status |
|---|---|---|---|---|
| [N20E-12-100](https://www.hestore.hu/prod_10042900.html) motor + encoder | 26 × 10 × 12 body, Ø3 D-shaft (H). The encoder board is 14.5 × 12 (H-doc). The 6-pin plug and cable leave from the back. 12 V DC, 100 RPM, rated torque 196 mN·m, 50 mA operating / 100 mA max (H). Same drawing and pinout as the N20E-06-100 it replaces (39 mN·m at 6 V). Gear ratio, encoder PPR and stall current aren't published. | H, [drawing](https://www.hestore.hu/prod_getfile.php?id=13746) | 26 + 8 encoder, 15 × 15 | ✅ |
| [N20-3PI-WHL](https://www.hestore.hu/prod_10042770.html) wheel | Ø42 × 18, D-bore press fit | H | 43 × 19 envelope | ✅ |
| [GG-KUB-30-B](https://kerekaruhaz.hu/spd/308640/GG-KUB-30-B-peremes-sullyesztheto-rogzito-furatos) ball transfer unit (not from HESTORE) | Pressed galvanised steel housing, steel ball, 75 kg load (other). Vendor drawing: Ø71.8 flange, 3.3 overall flange height, Ø45.06 cup 16.7 deep behind it, 35 overall; Ø30 ball, its tip 15 beyond the flange face (18.3 beyond the flange's back), 11.7 beyond the pressed ring around it; 3 × Ø5 holes. The Ø60 bolt circle is scaled off the drawing. Flange sheet thickness: **TBD, measure**. | other, vendor drawing | as drawn, ball down, flange screwed under the floor through a 1.7 mm printed spacer (ball tip 20 below the underside); cup through a Ø46 floor hole; 3 M4 heat-set inserts on Ø8 bosses | ⚠️ measure the flange sheet thickness (sets the M4 screw length) and the bolt circle |
| [TB6612FNG-M](https://www.hestore.hu/prod_10047992.html) motor driver (HW-166) | 20.5 × 20.5. Two loose 8-pin headers that **you solder**. Height with headers isn't published. | H | 20.5 × 20.5 × 10 | ⚠️ height: measure |
| [1000 µF / 16 V](https://www.hestore.hu/prod_10049933.html) capacitor | Ø10 × 13, 5 mm lead pitch, low ESR, 105 °C. Rated above the 12 V motor rail; the earlier 10 V part wasn't. No datasheet linked. | H | Ø10.5 × 17.5, lying behind the battery between the driver pocket and the switch-side encoder | ✅ |

## Power

| Part | Real size (mm) | Source | CAD reserves | Status |
|---|---|---|---|---|
| [2x18650-HOLDER](https://www.hestore.hu/prod_10041833.html) cell spacer (×4) | Interlocking organiser for 2× 18650 cells, for alignment while spot-welding. One sits at each of the pack's four cell-end planes and holds the two parallel cells. | H | inside the pack envelope | ⚠️ measure its thickness: it adds to the pack length |
| [TP-INR18650-35HE](https://www.hestore.hu/prod_10051020.html) cell (×4, 2S2P) | Ø18.6 × 65.3, flat top | H, [datasheet](https://www.hestore.hu/prod_getfile.php?id=22566) | Flat 2S2P pack, two rows of two cells end to end (raw ≈ 131 × 37.2 × 18.6): 142 × 41 × 21 in a floor cradle, held by two 20 mm hook-and-loop straps | ⚠️ conservative until a holder is measured |
| [HX-2S-JH20](https://www.hestore.hu/prod_10046818.html) BMS | 47.5 × 24 × 3.6, solder pads | H | 50 × 27 × 6, flat on top of the pack | ✅ |
| [USBC-2S-LI-BOOST](https://www.hestore.hu/prod_10051910.html) 2S USB-C charger | Dimensions not published. 5 V USB-C input, 0.9 A default charge current, 8.4 V default pack voltage. | H | temporary 35 × 22 × 6 on rails at the rear wall, USB-C port through a 13 × 8 slot | ⚠️ measure the received board |
| [SZ-08CV](https://www.hestore.hu/prod_10043183.html) step-up/down converter | 60 × 50.5 × 20, screw terminals | H, [drawing](https://www.hestore.hu/prod_getfile.php?id=21097) | 63 × 54 × 23 with airflow, rear bay, on 4 × 7 mm M3 standoffs (holes 45 × 37, Ø3.2), floor vents underneath | ✅ |
| [XL6009-UD](https://www.hestore.hu/prod_10048609.html) motor step-up/step-down converter | 49 × 24 × 13, 5–30 V input, 1.4–30 V output, max. 4 A (4 A only with heatsink and fan). Pads IN+, IN−, EN, OUT+, OUT−; EN left open keeps the output on. Set to 12.0 V. Replaces the DSN-1504-3A, whose output didn't suit. | H, [XL6009 datasheet](https://www.hestore.hu/prod_getfile.php?id=19505) | on two 4 mm printed standoffs (M2.5 self-tapping) in the front corner on the switch side, between the battery and the sensor mount; IN end toward the side wall, OUT end toward the centre. Holes Ø3.0, measured: 7.5 from the IN end and 3 from the rear edge, 7.5 from the OUT end and 3 from the front edge | ✅ holes measured |
| [SL 19123](https://www.hestore.hu/prod_10026600.html) slide switch | Body 12.8 × 6.7 × 6.7, slider 3.8 wide, stands 4.65 off the body, 2.2 travel; legs leave the back; 6 A / 28 V DC | H, [drawing](https://www.hestore.hu/prod_getfile.php?id=1590) | pocket behind the rear wall, slider through a slot in a 1 mm recess (stands 2 mm proud) | ✅ |

The battery is 4 × 18650 in a 2S2P configuration: 7.2 V nominal, 8.4 V fully charged, 6.8 Ah (~49 Wh). Charging is USB-C 5 V → USBC-2S-LI-BOOST → HX-2S-JH20 / battery pack. During operation, the protected pack feeds the SZ-08CV set to 5.1 V for the Raspberry Pi 5 / logic rail and the XL6009-UD set to 12.0 V for the TB6612 motor rail.

## Compute, sensors, audio

| Part | Real size (mm) | Source | CAD reserves | Status |
|---|---|---|---|---|
| [Camera Module 3 NoIR](https://www.hestore.hu/prod_10048880.html) | PCB 25 × 23.9 × 1.1, 11.5 overall, lens block 10.8, holes Ø2.2 | H, [RPi datasheet](https://www.hestore.hu/prod_getfile.php?id=19774) | 25 × 24, housing 11, holes 21 × 12.5 | ✅ (confirm the hole pattern) |
| [INMP441-M](https://www.hestore.hu/prod_10043182.html) microphone | Round board, about Ø14. Loose 6-pin header that **you solder**. The sound hole is underneath. | H photos, measure | 14 × 14 × 3 | ⚠️ measure |
| [MAX98357-M](https://www.hestore.hu/prod_10045704.html) amplifier | About 19.4 × 17.8 (Adafruit layout). Loose 7-pin header and 2-pin screw terminal that **you solder**. | H, other | 19 × 17 × 5 | ⚠️ height with the terminal |
| [3525 speaker](https://www.hestore.hu/prod_10049293.html) 4 Ω / 3 W | **35 × 25 × 6.5 rectangular box**. Fires from the large face. Adhesive mount, no screw holes. 165 lead with a 1.25 mm 2-pin plug. | H, H drawing | slide-in slot behind an oval grille in the left wall | ✅ |
| [Adafruit VL53L1X #3967](https://www.adafruit.com/product/3967) ToF (not from HESTORE) | Board 25.4 × 17.8, 4.6 with the sensor and STEMMA QT sockets (same side). 4 M2.5 holes 20.32 × 12.7, sensor in the centre. Loose 6-pin header that **you solder**. | [Adafruit fab print](https://learn.adafruit.com/adafruit-vl53l1x/downloads) | upright on 4 standoffs (3.5) in the sensor mount, 12 × 9 window | ✅ |
| Raspberry Pi 5 with a cooler or passive case of your choice (not from HESTORE) | Pi 5 board 85 × 56, holes 58 × 49 (M2.5). Reserve sized for the largest case considered, the JOY-IT RB-AlucaseP5-09: **91 × 65 × 34**. | [JOY-IT](https://joy-it.net/en/products/RB-AlucaseP5-09), checked 2026-10-23 | 91 × 65 × 34, centred on the Pi's board, so 10 mm toward the USB side of the 58 × 49 hole pattern (the holes sit 3.5 from the PCIe edge of the 85 mm board). Lifted on 4 × 15 mm spacers over the AI HAT+ 2 space (case bottom 80.1, top 114.1; 8.5–15.3 to the lid); interference-checked against the lid and the join screw paths | ✅ |
| Raspberry Pi AI HAT+ 2, 40 TOPS (**optional**, not from HESTORE) | Board 65 × 56.5, holes 58 × 49 inset 3.5 (the Pi's), PCIe FPC connector in a notch on the left edge. Heatsink 64 × 42.5 × 3.2 on 2 push pins (14 long). Board thickness, pin heads (Ø5.6, top 11.6 above the board) and the heatsink outline were scaled off the drawings, not dimensioned. | Raspberry Pi Ltd mechanical drawings (HAT and heatsink), supplied 2026-10-23 | On the 3 mm tray standoffs **under** the Pi, not on its GPIO: 10.5 mm air over the heatsink, 3.5 to the pin heads. Linked by the PCIe FFC only (a 180° U on the Pi's −X side, about 43 mm along its centre line), plus 5 V and GND jumpers. The space is reserved with or without the HAT. | ⚠️ FFC length and type not chosen |

## Enclosure hardware

| Part | Real size (mm) | Source | CAD reserves | Status |
|---|---|---|---|---|
| [RI M2,5x15 BB](https://www.hestore.hu/prod_10034409.html) spacer (×4, Pi) | M2.5 female–female, hex 5 AF, 15 long, nickel-plated brass (DREMEC). The page's spec table also says "Hosszúság 12": check the length you receive. | H | Ø5.77 (the hex's corners) × 15 between the HAT (or the tray standoffs) and the Pi case. Two of them stand 6 mm from the HAT heatsink's push pins, as on the Pi 5's own cooler: 0.3 mm at the hex corners, 0.7 across the flats. | ✅ (confirm length) |
| [Neodymium magnet V5-2-N38](https://orodian.hu/termek/neodimium-hengermagnes-5x2-mm-n38) (×4, two pairs) | Ø5 × 2, N38, axially magnetised (poles on the flat faces), Ni-Cu-Ni coated, 0.43 kg pull on steel | orodian.hu | Ø5.2 × 2.1 pockets: one in each front column, one in each boss under the lid | ✅ |

## Mass budget

The masses behind the centre-of-mass check in `cad/blender/build_mirae.py`, which places each one at its part's position in the model. Basis:

- **vendor**: published for this part
- **maintainer**: value supplied by the maintainer
- **verified equivalent**: published for a matching part with the same size and rating
- **strong estimate**: published for a closely comparable board
- **estimated**: no published value; weigh the part you have
- **computed**: from the part's size and material
- **volume**: printed part, from its STL volume × 1.24 g/cm³ (PLA) × 0.8 fill; your slicer's weight replaces it

| Part | Qty | Each (g) | Total (g) | Basis |
|---|---:|---:|---:|---|
| top-cover | 1 | 181 | 181 | volume (182.7 cm³) |
| pi-module | 1 | 206 | 206 | volume (207.8 cm³) |
| chassis | 1 | 174 | 174 | volume (175.9 cm³) |
| faceplate | 1 | 33 | 33 | volume (33.3 cm³) |
| sensor-mount | 1 | 10 | 10 | volume (10.4 cm³) |
| caster-spacer | 1 | 4 | 4 | volume (4.4 cm³) |
| SZ-08CV, with its heatsinks | 1 | 220 | 220 | maintainer |
| JOY-IT RB-AlucaseP5-09 | 1 | 205 | 205 | vendor |
| Battery pack, complete (cells, spacers, nickel strip, BMS, its wires) | 1 | 205 | 205 | maintainer |
| Raspberry Pi 5 board | 1 | 62 | 62 | maintainer |
| GG-KUB-30-B ball transfer unit | 1 | 220 | 220 | maintainer (ball 111, housing 109) |
| N20E-12-100 motor with encoder | 2 | 14 | 28 | strong estimate (same body as the 6 V version) |
| N20-3PI-WHL wheel | 2 | 19.4 | 38.8 | verified equivalent |
| XL6009-UD | 1 | 12 | 12 | strong estimate |
| AI HAT+ 2 with heatsink (optional) | 1 | 35 | 35 | estimated (board alone: 19, verified) |
| RI M2,5x15 BB spacer | 4 | 2.1 | 8.4 | computed |
| Hook-and-loop strap | 2 | 5 | 10 | estimated |
| Wiring harness | 1 | 30 | 30 | estimated |
| Screws and heat-set inserts | 1 set | 12 | 12 | estimated |
| 3525 speaker | 1 | 7 | 7 | verified equivalent |
| USBC-2S-LI-BOOST charger | 1 | 5 | 5 | estimated |
| Camera Module 3 NoIR + FFC | 1 | 5 | 5 | camera 4 (vendor) + 1 for the FFC |
| TB6612FNG-M with headers | 1 | 3 | 3 | strong estimate |
| 1000 µF / 16 V capacitor | 1 | 2 | 2 | strong estimate (a 10 × 16 part; this one is 10 × 13) |
| SL 19123 switch | 1 | 1.7 | 1.7 | vendor (TME) |
| Adafruit VL53L1X with header | 1 | 2 | 2 | vendor (1.8 bare) |
| MAX98357-M with header and terminal | 1 | 2 | 2 | strong estimate |
| INMP441-M | 1 | 2 | 2 | verified equivalent |
| Magnet Ø5 × 2 N38 | 4 | 0.3 | 1.2 | computed |
| **Total** | | | **≈ 1,727** | |

With these masses the centre of mass sits 36 mm ahead of the axle and 60 mm above the ground, and the caster carries 37% of the weight (see the stance notes in the [enclosure guide](../cad/README.md#stance-and-stability)). The printed parts are the largest estimated share. With the printed parts anywhere from 60% fill to solid, the build's checks still pass (caster 36–38%, against the 40% limit).
