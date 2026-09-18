# ThumbsUp v1 hardware review (2026-09-03)

Scope: the Grok-generated circuit (`tools/gen_skidl.py`, since deleted), its
supporting docs, and the tooling used to draw it.  Every finding below was
checked against the vendor datasheet in `datasheets/pdf/`, the AM32 source
(`Inc/targets.h`, `Src/main.c`, `Mcu/f421/Src/*.c` at `am32-firmware/AM32`
main), a SPICE simulation (`tools/spice/`), or the live LCSC/JLCPCB part
pages.  "Fixed" means the new `tools/sch/circuit.py` contains the change.

## 1. Defects that would have damaged hardware or prevented it from working

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 1 | **AP63205 FB pin left floating** (`nc_unused(buck)`). The fixed-5 V part regulates *on the FB pin*; V_FB is specified as 4.95–5.05 V and the application circuit ties FB to VOUT. Floating FB → converter runs open loop toward VIN → up to 12.6 V on Pico VSYS (abs max 5.5 V). | AP63205 DS Fig. 21, EC table "VFB … AP63205 4.95 / 5.00 / 5.05 V" | FB wired to +5V. |
| 2 | **Reverse-polarity P-FET installed backwards** (`vbat += q1["S"]`, `vdrv += q1["D"]`). With the pack on the source, the body diode conducts under reverse polarity. SPICE: −12.6 V pack → −11.9 V on the load. | `tools/spice/sim_rpp.py` | Pack on DRAIN, +VDRV from SOURCE, 100 k gate pull-down, 12 V zener G–S. SPICE: 0 V / 0 mA under reverse polarity, Vgs −9 V at 9 V pack. Extra 100 k G–S resistor removed (it halved the gate drive). |
| 3 | **Weapon-enable scheme violated FD6288Q abs max.** Switching the driver's VCC off while the AT32 keeps driving 3.3 V into HIN/LIN breaks "VIN: −0.3 … VCC+0.3 V". | FD6288 DS §3.1 | VCC P-FET kept (real hardware kill), plus Q49 holds the weapon AT32 in reset (all GPIO high-Z, FD6288 has 200 kΩ input pull-downs) whenever the enable is off. Enable = WEAPON_EN AND ARM via two AO3400A (Q47/Q48) so a floating Pico pin cannot arm the weapon. Bootstrap diodes fed from the switched VCC. |
| 4 | **BEMF/current scaling did not match the stock AM32 hex.** `AT32DEV_F421` does not define `MILLIVOLT_PER_AMP`/`TARGET_VOLTAGE_DIVIDER`, so the compile-time defaults apply: 20 mV/A and 110 (100 k/10 k). PARTS.md instead specified a 2 mΩ shunt read directly (2 mV/A) and a 10 k/3.3 k divider, which would require a custom firmware build — contradicting the "stock hex" goal — and gave 0.4 A per ADC count with no filtering. | `targets.h` lines 3267–3281, `main.c` 2158–2160 | 1 mΩ shunt (same part as the pack shunt) + INA180A1 (20 V/V) = 20 mV/A with RC to PA3; 100 k/10 k on PA6. Stock hex reads volts and amps correctly. |
| 5 | **No decoupling anywhere.** Only 4 capacitors in the whole design besides bootstrap caps: no AT32 VDD/VDDA caps, no FD6288 VCC cap, no INA226/IMU/flash/buffer caps, no buck input cap, single 22 µF output cap, no bulk at the pack entry or the bridges (PWR-4/PWR-5 SHALL). | AT32 DS §5.3.x Fig. 8, AP63205 DS §11, ADXL375 DS "Power supply decoupling" | 47 capacitors added (see sheets' decoupling strips). |
| 6 | **AT32 BOOT0 floating, no SWD headers, no NRST cap** (MOT-8 SHALL). BOOT0 has an internal weak pull-down but a motor driver is not the place to rely on it. | AT32 DS pin table note "B = … embedded weak pull-down" | 10 k BOOT0 pull-down, 100 nF on NRST, 1×5 SWD header per cell. |
| 7 | **Custom symbol library unreadable by KiCad** (`(version 20260306)` — a made-up future format). Every ERC run reported "library 'thumbsup' not found" and the AT32 symbol was missing 7 package pins (PA11, PA12, PA15, PB3, PB5, PB6, PB7). | `kicad-cli sym upgrade` → "Unable to load library" | Library regenerated (`tools/sch/symbols.py`, version 20241209) with all 33 pins; pin numbers re-verified against DS_AT32F421 Fig. 4 / pin table (VSS is the exposed pad only, pin 16 = PB2, BOOT0 = 31, PB4 = 27). |
| 8 | **SKiDL-generated hierarchy was broken**: 34 unconnected hierarchical sheet pins, 33 dangling labels, `3V3_MON` net with a single pin (the monitor divider was never created), `I_PACK+` silently merged into `VBAT_PACK`. | `kicad/thumbsup-erc.rpt` (old) | New generator; KiCad ERC and a SKiDL↔KiCad netlist equivalence check run on every build. |

## 2. Requirements that were silently unimplemented

| Req | Missing in the old netlist | Now |
|---|---|---|
| SEN-6 | 3V3 monitor divider | 10 k/10 k + 100 nF → GP27 |
| SEN-10 / MOT-10 | Board NTC | 10 k NTC / 10 k → GP28 (LED data moved to GP22) |
| C-7 | Power LED independent of firmware | R16 + D4 on +5V |
| §10 | ARM switch / connector and pull-up (the `ARM_N` net had no switch) | J2 + 10 k pull-up + 100 nF |
| §10 | Expansion header | 2×6: +5V, +3V3_A, GND, I2C, UART0 (GP12/13), GP10/11, RUN |
| MCU-2 | RUN/reset reachable | SW1 + RUN on expansion header |
| MOT-9 | Motor pads | J21/J31/J41 |
| PWR-4/5 | Entry and per-cell bulk | 470 µF entry, 470/470/1000 µF per cell + 2×10 µF MLCC at the drains |
| DS | LSM6DS3 SDx/SCx "connect to VDDIO or GND" were left floating | tied to GND |
| DS | INA226 input filters (10 Ω + 100 nF) | added on all four channels |

## 3. Design changes beyond bug fixes (call these out if you disagree)

* **Separate 3.3 V rails**: `+3V3_A` (INA226 ×4, IMU, high-g) and `+3V3_MCU` (3× AT32, flash) from two AP2112K. PWR-7 asked for one LDO; three PWM-timer MCUs on the "analog" rail is a poor idea for an instrumentation-first board and the second LDO costs nothing. AT32 run current is 16.7 mA typ at 120 MHz (DS Table 17), so each LDO stays well inside its SOT-23-5 budget.
* **Schottky between +5V and Pico VSYS** (D3). Without it USB VBUS back-feeds through the Pico's own diode into +5V, then through the AP63205 high-side body diode into +VDRV, VBAT and the FD6288 VCC pins. The Pico datasheet recommends exactly this diode when VSYS is externally powered. Consequence: on USB alone only the Pico runs; bench-test sensors and ESCs with the pack or a bench supply on the XT30.
* **EN divider 100 k / 20 k** instead of 470 k / 100 k. SPICE with the datasheet's 1.5 µA + 4 µA EN currents: the old values switch on at 6.0 V and *off at 3.7 V*, not "~6.7 V"; the new ones give 6.9 V on / 6.05 V off (and 470 k 0402 is no longer a JLC Basic part).
* **LED data on GP22, NTC on GP28/ADC2**, IMU INT1 → GP2, ADXL375 INT1 → GP3 (data-ready for 1 kHz sampling). `firmware/include/config.h` must follow PINMAP.md.
* **Rboot 10 Ω** (2.2 Ω 0402 is not a JLC part); with 100 nF the 2 µs low-side window at 95 % duty is still ~2 τ. SPICE: 0.46 V droop at the end of a 39.6 µs on-time at 9 V VCC, 3.7 V above the FD6288 VBS UVLO; 100 nF is adequate, 1 µF is not needed.
* **BAT54S BEMF clamps dropped**: with 10 k series resistance the injected current into the AT32's ESD diodes on a ringing phase node is ~1 mA, which is how AM32 reference hardware is built.
* **LMV321 rejected for the current sense**: V_OS up to 7 mV × gain 10 = 0.7 A of offset. INA180A1 is ±150 µV.

## 4. Things I could not verify — check before ordering

* INA180A1IDBVR LCSC number (placeholder `C1361247?` in the BOM field).
* FD6288Q exposed-pad size (Fortior drawing is an image; footprint uses EP 2.7×2.7 mm) and whether the pad is COM. HX6288 (C54423134) is pin-for-pin identical per its datasheet table but its EP was not confirmed either.
* SK6812MINI-C pad geometry vs KiCad's `LED_SK6812MINI_PLCC4_3.5x3.5mm` (part is 3.5×3.7 mm).
* Inductor footprint: `L_Changjiang_FNR4020S` used for the FHD4020S-4R7MT (both 4×4×2 mm; check pads).
* JLC stock: FD6288Q C328453 is **out of stock**, ADXL375 179 pcs, 74AHCT1G125GW 470 pcs.
* AP40P05 is a 65–120 mΩ SOT-23 part (Vgs(th) −1.0…−2.5 V, Id −5 A). Fine for the logic path (< 1.5 A) and the weapon VCC switch, but it is not suitable if you ever put the motor current through it.
* Electrolytics: none of the LCSC candidates publish ESR; measure ripple on the bench (PWR-5 already says so).

## 5. Tooling

Old: `gen_skidl.py` (SKiDL 2.3.0 `generate_schematic`) + `gen_kicad.py` (1300-line hand
sexpr writer, "do not run"). The SKiDL placer produced sheets that were either a
single unrouted clump or labels-only, could not connect its own hierarchical
pins, and left the file dependent on an unloadable library.

Alternatives looked at (all current as of 2026-09):

| Tool | Verdict for this board |
|---|---|
| SKiDL 2.3.0 auto-schematic | Keeps the netlist language, but the placer/router is the problem. Kept SKiDL **only** for connectivity/ERC/netlist. |
| atopile | No schematic output by design (netlist + layout). Not a fit for "reviewable schematic". |
| tscircuit | Schematic autolayout is documented as beta; no `.kicad_sch` export path confirmed. |
| circuit-synth | Wraps `kicad-sch-api`; placement quality not documented; adds a second circuit language. |
| kicad-sch-api 0.5.6 | Writes real `.kicad_sch` (wires, labels, power symbols, sheets, no-connects), embeds library symbols, KiCad 10 opens it. Its `get_pin_position` does not flip the Y axis (verified against a `kicad-cli` netlist export), so `draw.py` computes pin geometry itself. |
| KiCad IPC API (kipy) | Needs a running KiCad; no headless use. |

Chosen pipeline (`tools/sch/`): `circuit.py` (SKiDL, the only place connectivity lives) →
`layouts.py` (explicit placement per sheet, hand-routed where it matters, automatic
labels/power symbols/no-connects elsewhere) → `build.py` (KiCad ERC, `kicad-cli`
netlist export, **netlist equivalence check against SKiDL**, PNG previews).
Placement is code, so it is reviewable in diff and reproducible; the schematic is
never edited by hand.

Result on 2026-09-03: KiCad ERC 0 errors (7 four-way-junction warnings, 3 warnings for
bidirectional address-strap pins tied to GND), SKiDL↔KiCad netlist equivalence OK over
169 nets / 277 parts.

---

# 6. Layout-readiness review (2026-09-03, rev v1.1)

Second pass, run as a multi-agent workflow: 10 independent review lenses (power tree,
AM32 cell vs firmware source, power stage, sensors/I2C, safety/arming, Pico I/O, BOM &
footprints, requirements traceability, schematic quality, layout inputs) → merged into 74
findings → each finding checked by two adversarial verifiers (evidence lens, circuit lens)
→ synthesis + completeness critic.  Independently re-checked by hand before any change:
F01, F03 (SPICE), F04, F05, F24 (datasheet).  Verification statistics: see §6.5.

## 6.1 Blockers found and fixed

| # | Finding | Evidence | Fix (in `circuit.py` / `symbols.py` unless noted) |
|---|---|---|---|
| F01 | **All 18 bridge FETs miswired.** `Q_NMOS_GSD` (1 = G, 2 = S, 3 = D) on the PQFN-8-EP footprint whose pads are 1–4 leads + 5 tab; the HYG015N04LS1C2 is S S S G / D-tab. Gate on a source lead, drain on a source lead, real gate and drain tab unconnected. The SKiDL↔KiCad equivalence check cannot see pad functions. | Huayi DS p.1; `PQFN-8-EP_6x5mm_P1.27mm_Generic.kicad_mod` pads | Custom symbol `thumbsup:HYG015N04LS1C2` (1,2,3 = S stacked, 4 = G, 5 = D). |
| F03 | **Weapon VCC P-FET never turned off.** R440 100 k pull-up was loaded by the Q49 divider (R443 100 k + R444 47 k) → gate at 0.6 V_DRV, Vsg 2.4–5.5 V, W_VCC permanently on. Only the reset hold stood between the operator and the weapon. | ngspice: Vsg 3.64 V @ 9 V, 5.10 V @ 12.6 V | R440 → **4.7 k** (Vsg ≤ 0.42 V off, Q49 gate ≥ 1.86 V at a 6 V pack, 39 mW on). Added **Q50** (G = ARM_N → NRST) so "link removed → reset" no longer shares a node with the VCC switch (F26). |
| F04 | **SK6812MINI-C symbol vs footprint mismatch.** OPSCO numbering (1 DIN, 2 VDD, 3 DOUT, 4 GND) on KiCad's SK6812MINI footprint (1 DOUT, 2 VSS, 3 DIN, 4 VDD) → +5V on the LED's GND corner; pads also the wrong size (asymmetric OPSCO terminations). | OPSCO DS §6 land pattern | Footprint `thumbsup:LED_SK6812MINI-C` drawn from the DS pattern, numbered per the DS, pin-1 mark at the DIN corner. |
| F05 | **XT30 polarity reversed** vs the KiCad AMASS footprint ('+' = pad 2). The Amass drawing carries no polarity mark, so the library convention (consistent across XT30PW-M/-F and XT30U) is followed and must be checked on a physical part. | `AMASS_XT30PW-M…kicad_mod` fp_text | `vbat_pack += j1[2]`, note on the symbol, silk '+' in LAYOUT.md, open item in §13. |
| F06 | **Reset switch on the wrong footprint** (XKB TS-1187A 5.1 × 5.1 mm 4-terminal on the 2-pad Omron B3U pattern). | JLC C318884 page | `Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A` (KiCad library, pads 1,1,2,2). |
| F02/F08/F39 | **Bulk electrolytics**: through-hole radial cans (8 × 12 / 10 × 16 mm, ~0.6 A ripple, no ESR spec) on an SMD footprint. | LCSC C43839 / C503217 pages; ripple calc 10 A × √(D(1−D)) ≈ 5 A RMS | Panasonic **EEHZK1E471P** hybrid polymer 470 µF 25 V (20 mΩ, SMD 10 × 10.2, JLC Extended, C242138), 1 per drive cell, 2 on the weapon, 1 at the entry; alt KNSCHA 118EC421 (14 mΩ / 4 A). |

## 6.2 Majors fixed

* **F07/F19 Kelvin sensing not expressible** — sense nets `PACK_S±`, `I_x_S±` added, joined to the current nets only through `NT1–NT41` net-ties (0.5 mm pads) that layout must place on the shunt pads; shunt footprint `thumbsup:R_2512_Shunt_Kelvin` (3.1 × 4.0 mm pads). INA180 IN− and the INA226 filters now sense from these nets.
* **F09 ARM link pull-up on +3V3_A** (rail loss read as "link present") — R22 moved to the Pico's own 3V3 (pin 36).
* **F10 motor pads were 2.54 mm pin headers** — `thumbsup:MotorPads_1x03_P5.00mm` (2 mm holes, 4.5 mm pads, 4 × 3 mm lands).
* **F11 INA180 LCSC placeholder** was a 0 Ω resistor network — now **C122228** (INA180A1IDBVR, 15 k in stock).
* **F12 FD6288 exposed pad missing from the symbol** — pin 25 EP added and tied to COM (HX6288 DS confirms EP = COM); driver ordered as HX6288 C54423134 (FD6288Q C328453 alternate, out of stock).
* **F13 no power link** — J4 XT30 loop plug added between the entry filter and the shunt (PWR-2); may be DNP if J1 is declared the disconnect.
* **F14 buck EN/UVLO 6.05 V off** would reboot logic on a 3 V hit sag from a 9 V pack — R11 → 27 k (on 5.40 / off 4.62 V, SPICE `tools/spice/sim_en_uvlo.py` case (c)).
* **F15 10 k DShot pull-downs break AM32 1-wire serial** (AT32 pull-up 65–130 k) — R201/R301/R401 now **DNP** (footprints kept); 100 Ω series resistors R24–R26 added at the Pico for contention limiting (F23).
* **F16 firmware migration list** — full table in PINMAP.md (LED pin, `BATTERY_DIVIDER 5.545`, WEAPON_EN, DShot drive, PIO budget, bench guard).
* **F17/F18/F20/F21 layout inputs** — LAYOUT.md written (net classes and currents, ground/Kelvin strategy, stackup 4-layer 2 oz outer, placement/thermal rules, DFM); H1–H4 M3 holes and FID1–FID3 fiducials are now parts so they survive regeneration.

## 6.3 Minors fixed

F25 test points (22: rails, DShot, I2C, ARM_N, per-cell ISENSE/VSENSE/PB6-telemetry/I_x+, WEAPON_EN bench enable), F27 power LED from +VDRV (pack-present), F28 bootstrap R 10 → 2.2 Ω (2 V of drive lost at 48 kHz otherwise; SPICE), F29 low-side Rgs returned to the FET source, F30 FD6288 VCC 10 µF, F33 LDO input caps 0603, F34 buck input caps 10 µF 50 V 1206, F37 100 nF on RUN, F41 sim cases, F43 duplicate wire segments (drawer dedupe), F44 label stagger on adjacent pins, F45 per-part `Note` property, F49 TP40, F70/F71 value strings ("1mΩ"), title blocks with rev/date, docs (F40, F42, F62).

## 6.4 Accepted as-is (documented, no hardware change)

F22 USB-only bench mode (firmware gates peripherals on 3V3_MON), F31 INA180 input kick (10 Ω series would cost 40 mA of offset through the 80 µA bias), F35 ADXL375 800 Hz on I2C, F36 NTC divider centre, F46/F52/F53/F54 pack-path behaviour (reversed pack destroys the board; TVS 3S only), F47 Pico antenna keep-out, F48 ADC3 read under the CYW43 lock, F56 bootloader parking on idle-high, F57 bus-side current semantics, F58 AM32 EEPROM defaults, F59–F61, F63 FD6288 VIH margin, F64 pack-V calibration, F66/F67 Q46 gate stress (Vgs ±20 V, 24 V only during a TVS event), F68/F69 firmware notes, F72–F74 cost/thermal/DFM tables (moved into LAYOUT.md).

## 6.5 Verification statistics

115 raw findings from 10 lenses → 74 after merge → 148 verifier votes requested, 132 delivered
(the session limit cut the last 16, all on informational notes F66–F74, plus the synthesis
agent; synthesis was done by hand from the votes).  **67 findings confirmed by both verifiers,
0 refuted.**  Severity changes by the verifiers: F39 minor → blocker/major (tall THT cans),
F19 major → minor, F24/F28/F33/F34 minor → note, F30 and F63 minor/note → "not a defect" by one
verifier each (F30 changed anyway: 10 µF costs nothing; F63 left as is).  Every fix above was
re-checked against the verifiers' `corrected_fix` text; the only deliberate deviation is F31
(no series R on the INA180 input — 10 Ω against the 80 µA bias would add 0.8 mV = 40 mA of
offset, worse than the transient it protects against).

Post-fix build: KiCad ERC **0 errors** (2 four-way-junction warnings at genuine crosses, 3
"bidirectional pin tied to ground" warnings on address straps), SKiDL↔KiCad netlist
equivalence **OK (324 parts, 179 named nets)**, new `build.py` pad-mapping assertion for every
FET (symbol pin numbers vs the PDFN / SOT-23 pinout) passes.

# 7. Layout (2026-09-04, rev v1.2)

The board was laid out by generated tooling (`tools/mech`, `tools/pcb`; see LAYOUT.md).
Circuit changes forced by the mechanics, all made in `tools/sch/circuit.py` and re-verified
by ERC + the SKiDL/KiCad netlist equivalence check:

| Change | Why |
|---|---|
| J4 (POWER LINK XT30) and C4 (entry can) removed; J1 alone, mating through a slot in the back wall, is the SPARC disconnect | the 104.5 × 37.5 mm bay has no room for a second XT30, and one connector at the wall is the simpler disconnect |
| C426 removed; C425 is one KNSCHA 118EC421 (4 A ripple); all three cans sit on the single VBAT pour | area; the L and W cans share the top-left VBAT pour, the R can sits at the R block and is fed by the In2 bus |
| `MotorPads_1x03_P5.00mm` → `MotorHoles_1x03_P5.90mm` (2 mm holes between the FET rows) | the only way three phase nodes leave a 2 × 3 FET block on the outer layers |
| Net-ties on `NetTie-2_Kelvin_0.4mm` (copper-only pads in the shunt pad gap) | tie pads overlapping the shunt pads are DRC shorts; the gap is the Kelvin point the shunt vendor recommends |
| H1–H4 M3 → H1–H3 M2.5 at chassis bosses we add to the print; SWD headers → 1 × 5 pad rows; test points cut from 22 to 12 (rails, DSHOT_L, L cell, WEAPON_EN) | area; the bottom side is fully packed even so |
| Assembly both sides (ICs and passives on the bottom, ≤ 2.5 mm under 3 mm standoffs) | the top is FETs, shunts, cans, connectors and the Pico |
| I_L+/I_R+/I_W+ labelled on the bridge sheets | the shunt's hot node was auto-named, which broke the POWER net-class match |

Deviations from the v1.1 layout brief (LAYOUT.md §1–§5 of that revision): the L4 "VBAT /
phase mirror pours" were dropped (the bottom is the parts side; the outer-layer 2 oz pours
plus the In2 bus carry the currents; the drain MLCCs sit on the bottom under the tabs with a
via each); gate drive uses one via per gate (unavoidable with the FETs on top and the drivers
underneath); the R block's I_R+ band is 1.6 mm at the second column's gate notch (only the
third column's current crosses it).

Checks run on the generated board: `placement.check` 0 problems (outline, courtyards,
through-holes, Pico RF/antenna keep-outs, tall parts under the drum); chassis fit check 0
offending cells; KiCad DRC clean before routing; routing / DRC / unconnected statistics of
the final run are in the build log and `kicad/drc.json`.
