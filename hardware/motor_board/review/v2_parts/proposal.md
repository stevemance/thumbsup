# v2 re-layout: smaller-footprint part proposal (motor board)

Status: **proposal only**. No design file was changed.  Date 2026-09-29.

## How this was checked

* **Design side:** `design/motor_board.py` (roles, pin maps), `design/bom.csv`, `design/calcs.md`,
  `DESIGN.md` §3.1–§3.3, §6, §7 and the earlier BOM reviews (`review/r5_bom.md`, `r6_parts_lookup.md`,
  `round2_e_bom.md`, `round11_a_hardware.md`).
* **Stock and class:** JLC SMT-library API (`selectSmtComponentList/v2`), queried by exact C-number on
  2026-09-29.  "Stock" = JLC stock / presale.  "Extended" means a $3 loading fee per unique line in
  Economic PCBA.
* **Ratings:** LCSC product-detail API parameters, plus the datasheets I downloaded and read:
  TI SCAS283W (SN74LVC08A, pin table and BQA0014A drawing), Nexperia PMEG4030ER, MDD SS34 and DSK34,
  onsemi SS34FA, Panasonic ZK series table, ZE ZEMS404030 / ZEMS322520, MetalLions MTQH404030, and Diodes
  74LVC1G08.
* **MLCC DC bias:** Samsung's own model data.  This is the curve data embedded in
  `product.samsungsem.com/mlcc/<part>.do`.  The Murata and TDK product pages would not serve data to a
  script, so their curves are **not** verified.
* **Footprint areas:** courtyard bounding boxes of the stock KiCad footprints in
  `/usr/share/kicad/footprints` and of the project's `motor_board.pretty`.  These are courtyard areas.
  The mating clearance that connectors need in front of them is not included and is noted separately.
* **Hot-plug re-simulation:** I ran a scratch copy of `spice/sim_hotplug.py` in /tmp, with C1, the VBAT
  MLCCs and the VM-filter capacitance made into parameters.  The unmodified copy reproduces
  `spice/hotplug.out` exactly.  The results are in the table below.

| Sim variant (peak V/µs at the DRV8316 VM pins; limit 4) | re-close, typ. UVLO | re-close, min UVLO (C1 −40 °C ESR) | loaded bounce, ESR ≤ 40 mΩ | bounce, 0 °C bound | bounce, −40 °C limit |
|---|---|---|---|---|---|
| As designed (C1 330 µF; 12 µF on VBAT; 16 µF per VM branch) = `hotplug.out` | 0.66 | 2.09 | 1.66 | 2.26 | 2.66 |
| C1 → 220 µF, ESR × 1.35 (EEHZK1V221UP) | 1.14 | 2.19 | 1.89 | 2.43 | 2.74 |
| C25/C26/C31 → 0805 50 V only (VBAT 5.6 µF) | 0.69 | 2.17 | 1.66 | 2.28 | 2.77 |
| **Current 1206 parts at Samsung's DC-bias value** (6.6 µF VBAT, 8.8 µF per VM branch) | 1.03 | 3.23 | 2.38 | **3.39** | **4.15** |
| All 1206 → 0805 50 V (5.6 µF VBAT, 7.5 µF per VM branch) | 1.15 | 3.65 | 2.60 | 3.75 | **4.64** |
| VM branch → 2 × 1210 50 V (14 µF), VBAT caps as the Samsung row | 0.75 | 2.40 | 1.80 | 2.51 | 3.03 |
| C1 220 µF + 0805 everywhere | 1.87 | 3.36 | 3.03 | **4.07** | **4.80** |

> **Finding outside the scope of the swap (please read): the existing 10 µF 50 V 1206 parts are probably
> about half the capacitance the design assumes.**
>
> * **What the design assumes.** DESIGN §3.3, the C308 comment and calcs §7 assume "~4 µF each at
>   16.8 V, ~16 µF per drive".
> * **What Samsung's own model says.** For **CL31A106KBHNNNE (C13585)** it gives **−78 % at 16.8 V,
>   i.e. ~2.2 µF**.  That is ~8.8 µF per drive, and ~6.6 µF on VBAT instead of 12 µF.
> * **What happens with those values.** The worst in-environment case (0.3–0.8 ms loaded bounce, C1 at
>   its 0 °C bound) rises from 2.26 to **3.39 V/µs**.  The −40 °C case reaches **4.15 V/µs**, which is
>   over the 4 V/µs abs max (outside the 0–50 °C environment).
> * **What already agreed with it.** round11_a N-07 already showed 8 µF → 3.47 V/µs.  The r5 estimate
>   (4–5.5 µF) was a generic class curve marked UNVERIFIED.
> * **Next step.** Confirm this with a second source (Murata/TDK curve, or a bench C–V measurement of a
>   biased part) whatever you decide on item 8 below.  The 2 × 1210 option in item 8 fixes it.

---

## 1. U6 — SN74LVC08APWR (TSSOP-14, 43.4 mm²)

**Requirement.** Three 2-input AND gates.  VCC = 3.3 V.  24 mA drive is plenty, since each output drives
one DRV8323 INLx input.  The unused 4th gate has its inputs tied to GND (pins 12/13) and its output (11)
left NC.

| Rank | LCSC | MPN / maker | Package | Ratings vs original | JLC stock / class | KiCad footprint | Area saved | Risks |
|---|---|---|---|---|---|---|---|---|
| **1** | **C31971766** | **SN74LVC08ABQAR**, TI | WQFN-14 **BQA** 2.5 × 3 × 0.8 mm, 0.5 mm pitch, EP 1.0 × 1.5 | **Same die and same datasheet (SCAS283W).**  1.65–3.6 V, ±24 mA.  **Pin numbers 1–14 are identical** to the TSSOP (1A=1 … GND=7 … VCC=14), so the netlist is unchanged except for the thermal pad (pin 15).  TI: "thermal pad can be connected to GND or left floating" → tie it to GND | 2,984 / 2,984, Extended | `Package_DFN_QFN:DHVQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm`.  Its pad placement matches BQA0014A: 1/14 on one short side, 2–6 left, 7/8 other short side, 9–13 right | 16.8 mm² → **26.6 mm²** | Leadless, bottom-side placement (0.8 mm tall, fine).  Add pad 15 = GND to the U6 pin map and `parts.py`.  Stock is 2,984 (fine for a few boards) |
| 2 | C460522 ×3 | 74LVC1G08SE-7, Diodes | 3 × SOT-353 | 1.65–5.5 V, ±32 mA (better).  Pinout 1 A, 2 B, 3 GND, 4 Y, 5 VCC.  **The unused gate disappears** (no tie-offs) | 9,123 / 9,072, Extended | `Package_TO_SOT_SMD:SOT-353_SC-70-5` | 3 × 6.9 + 2 extra 100 nF 0402 ≈ 24 mm² → ~19 mm² | Two more decoupling caps and two more placements.  Each gate can sit at its DRV8323 INL pin, which helps routing |
| 3 | C150443 ×3 | 74LVC1G08FW5-7, Diodes | 3 × X1-DFN1010-6 (1 × 1 mm) | Same as #2 | 4,809, Extended | custom (0.35 mm pitch) | ~30 mm² | Very fine-pitch leadless: assembly and inspection risk.  Not recommended |

Rejected:
* Nexperia 74LVC08ABQ (C548063): 3 in stock.
* SN74LVC08ARGYR VQFN 3.5 × 3.5 (C2876771): 72 in stock.

**Recommend #1.**

## 2. D2 — SS34 (MDD, SMA, 24.5 mm²), buck catch diode

**Requirement.**
* ≥ 40 V.
* ~0.32 A average in normal operation (0.45 A out × (1 − D)).
* Up to ~1.2–1.7 A almost continuously into a shorted +5V (calcs §3).
* The original is 40 V, 3 A, VF 0.55 V @ 3 A, Tj max **125 °C**, RθJA 70 °C/W (5 × 5 mm pads).

At 1.5 A the diode dissipates ~0.6–0.7 W.  The cathode sits on the SW node, which has to stay small, so
all of the options rely on the anode/GND copper and on the short time to buck thermal shutdown.

| Rank | LCSC | MPN / maker | Package | Ratings | JLC stock / class | KiCad footprint | Area saved | Risks |
|---|---|---|---|---|---|---|---|---|
| **1** | **C389355** | **PMEG4030ER,115**, Nexperia | CFP3 / SOD-123W 2.6 × 1.7 × 1.0 mm | 40 V, IF(AV) 3 A, **VF 380 mV typ / 440 max @ 1 A**, 460/540 @ 3 A (lower than SS34).  IFSM 50 A.  **Tj 150 °C**.  Rth(j-sp) 18 K/W; Rth(j-a) 130 K/W (1 cm² cathode pad) / 220 K/W (min pad) | 12,169 / 12,097, Extended | `Diode_SMD:Nexperia_CFP3_SOD-123W` (pad 1 = K) | 9.9 mm² → **14.6 mm²** | Higher Rth(j-a) than SMA.  In a hard +5V short: ~0.6 W × ~130 K/W → Tj ≈ 50 + 80 = 130 °C, under the 150 °C limit (the SS34's limit is 125 °C).  Give the anode a GND pour with vias |
| 2 | C41029 | DSK34, MDD (same maker as the current SS34) | SOD-123FL | 40 V 3 A, VF 0.55 V @ 3 A, IFSM 80 A, **Tj 150 °C**, RθJA 80 °C/W typ (mount condition not stated) | 282,133, Extended | `Diode_SMD:D_SOD-123F` | 10.1 mm² → 14.4 mm² | Huge stock.  The thermal-note condition is missing from the datasheet |
| 3 | C719833 | SS34FA, onsemi | SOD-123FL | 40 V 3 A, VF 0.50 V @ 3 A, Tj 125 °C, RθJA 152 °C/W (JESD51-3) | 8,711, Extended | `Diode_SMD:D_SOD-123F` | 14.4 mm² | Highest RθJA of the three.  Tj max only equals the SS34's |

Also available: PMEG4030EP (SOD-128, C96234, 29 k stock).  It is thermally stronger but only saves
5.6 mm².  **Recommend #1**, with #2 as the high-stock fallback.

## 3. L1 — FNR5040S220MT (5 × 5 × 4 mm, 30.8 mm²)

**Requirement.**
* 22 µH (L min 20.9–23.9 µH, calcs §3).
* **Isat ≥ 1.6 A guaranteed** (TI SNVSA24 9.2.2.2; buck current limit 1.7 A max).
* The original's DCR is ≤ 0.17 Ω.

**No 4 × 4 mm wire-wound ferrite 22 µH part at JLC meets 1.6 A.**  I scanned all ~5,000 "22uH" listings;
the 4030 ferrites top out at Isat 1.2–1.4 A, and SWPA4030S220MT is 1.3 A.  **Molded metal-alloy parts
do meet it**, with a large margin.

| Rank | LCSC | MPN / maker | Size | Ratings | JLC stock / class | KiCad footprint | Area saved | Risks |
|---|---|---|---|---|---|---|---|---|
| **1** | **C49009291** | **ZEMS404030-220M**, ZE | 4.1 × 4.1 × 3.0 mm, molded | 22 µH ±20 %.  **Isat 3.5 typ / 3.1 A min** (−30 % L, same definition as the FNR's 1.6 A).  Irms 2.6 / 2.3 A (ΔT 40 K).  DCR 190 typ / **220 mΩ max**.  −55…+125 °C.  AEC-Q200 test list.  Land: A 4.10, B 1.30, C 4.10 | 2,304 / 2,304, Extended | `Inductor_SMD:L_Changjiang_FTC404030S` (pads 1.4 × 4.1 at ±1.35 = the same 4.1 mm outer span) | 21.3 mm² → **9.5 mm²** | DCR max 220 vs 170 mΩ: +11 mW at 0.45 A (0.45² × 0.05), negligible.  Metal-alloy cores saturate softly and hold Isat when hot (better than ferrite in the +5V-short case).  Core loss at 0.7 MHz with 0.26 A p-p ripple is small.  Lesser-known maker |
| 2 | C51883186 | MTQH404030S220MBT, MetalLions | 4.1 × 4.1 × 3.0 | Isat 3.4 / 3.0 A min, Irms 2.5 / 2.2, DCR 190 / 220 mΩ | 1,931, Extended | same | 9.5 mm² | as #1 |
| 3 | C48945865 | ZEMS322520S220MBCA, ZE | 3.2 × 2.5 × 2.0 (1210), molded | Isat 2.1 / **1.8 A min** (meets 1.6 A).  Irms 1.9 / 1.6 A.  DCR **315 / 364 mΩ** (2× the original) | 5,529, Extended | `Inductor_SMD:L_Changjiang_FTC322520S` | 11.2 mm² → 19.6 mm² | **Not equal or better on DCR/thermal:** ~+40 mW loss at 0.45 A (~1.5 % efficiency), and Irms min 1.6 A is marginal for a sustained 1.7 A +5V short.  Only take it if the area is critical.  (Changjiang's own FTC322520S220MBCA, C53281638, 1,153 in stock, is the exact match for that KiCad footprint, but its datasheet is image-only and I could not verify it) |

**Recommend #1.**

## 4. J4 — JST XH 5-pin side entry S5B-XH-A (C263757, THT, 198.9 mm²)

**Requirement.**
* The 4S pack's balance plug is JST-XH (XHP-5).
* Current is tiny: U8 draws µA; the peak is the ≤ 168 mA C9 hot-plug pulse through R11; D5 carries
  ~160 mA in the mis-wired case.
* THT is acceptable.

| Rank | LCSC | MPN / maker | Type | Ratings | JLC stock / class | KiCad footprint | Area saved | Risks |
|---|---|---|---|---|---|---|---|---|
| **1** | **C157991** | **B5B-XH-A(LF)(SN)**, JST (genuine) | XH 2.5 mm **vertical THT** | 3 A/pin, 250 V.  **Mates the pack's XH plug directly (no adapter)**.  Same pin 1–5 order | 71,837 / 64,103, Extended | `Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical` | 107.3 mm² → **91.6 mm²**, plus no plug-approach zone at the board edge | Plug enters from above: LCSC gives the header as ~7 mm tall, and the mated plug plus wire bend needs more.  Check the lid/chassis height over J4.  Still THT (hand-solder or JLC THT), as today |
| 2 | C189891 | BM05B-GHS-TBT, JST | GH 1.25 mm vertical SMD, latching | 1 A/pin, 50 V (plenty) | 12,343, Extended | `Connector_JST:JST_GH_BM05B-GHS-TBT_1x05-1MP_P1.25mm_Vertical` | 70.6 mm² → 128.3 mm² | **Needs an XH→GH adapter pigtail** (an extra connector pair in the cell-tap path, and a pin order you must keep: B− = pin 1).  4S packs ship with XH |
| 3 | C189896 / C157993 | SM05B-GHS-TB (GH R/A SMD) / B5B-PH-K-S (PH 2.0 vertical THT) | — | GH 1 A / PH 2 A | 48,203 / 160,933, Extended | `JST_GH_SM05B-GHS-TB_1x05-1MP_P1.25mm_Horizontal` / `JST_PH_B5B-PH-K_1x05_P2.00mm_Vertical` | ~130 / 128 mm² | Same adapter caveat.  The GH R/A needs front mating space |

SMD XH clones (e.g. Megastar ZX-XH2.54-5PLT, C7429683) are **larger** (17.5 mm wide with solder tabs)
than the THT vertical header.  **Recommend #1**: it keeps the direct pack mating.

## 5. C1 — 330 µF 35 V hybrid polymer EEHZK1V331P (10 × 10.2, 148.5 mm²)

**Requirement.**
* ≥ 35 V (the SMBJ20A clamps at 32.4 V).
* Bus bulk for the ~8 A rms weapon ripple (calcs §7).  At 24 kHz the MLCCs present ≥ 0.7 Ω against
  C1's ~28 mΩ, so C1 carries almost all of it; this is already above C1's 2.8 A rating during bursts.
* Its ESR sets the VM dV/dt in the hot-plug and bounce cases.

**No functionally identical smaller part is stocked.**  I scanned the whole JLC hybrid-polymer category
for ≥ 220 µF at 35–50 V.
* Every 330 µF / 35 V SMD part is 10 mm diameter (10 × 10 to 10 × 12.8).
* The 8 mm SMD parts stop at 220 µF.
* No taller 8 mm × 330 µF part is stocked.

| Rank | LCSC | MPN | Size | Ratings vs original (330 µF / 20 mΩ / 2.8 A @100 kHz 125 °C) | JLC stock | Area saved | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | C454287 | Panasonic **EEHZK1V221UP** (same ZK series) | 8 × 10.2 | 220 µF (−33 %), ESR 27 mΩ (+35 %), ripple **2.0 A** (−29 %), 4000 h @ 125 °C | 967 / 923, Extended | `Capacitor_SMD:CP_Elec_8x10.5` 110.7 mm² → 37.8 mm² | **Not recommended as a like-for-like swap.** |
| 2 | C46528088 | KNSCHA 118EC436 | 8 × 10.5 | 220 µF, 27 mΩ, 1.6 A @100 kHz, 4000 h @ 105 °C | 1,685, Extended | 37.8 mm² | Worse than #1 |

**Why EEHZK1V221UP is not recommended.**
* **Hot plug.** The scratch re-simulation stays under 4 V/µs: worst in-environment bounce 2.26 →
  2.43 V/µs, min-UVLO re-close 2.09 → 2.19, −40 °C 2.66 → 2.74.  The bounce dips deeper, though
  (4.4 → 3.7 V before re-close).  Combined with the realistic MLCC values it reaches 3.68 V/µs at 0 °C
  (4.26 at −40 °C).
* **Ripple heating.** ~35 % more heating on a lower rating, in a part that is already over-stressed
  in weapon bursts.
* **If you still want it.** It needs:
  * `sim_hotplug.py` re-run and committed with `cb` = 220 µF and ESRs scaled;
  * calcs §7/§9 updated (~374 → ~264 µF: the bleed τ, the soft-start current and Q7's energy all
    change);
  * a thermal check of C1 during weapon bursts.

**Recommend: keep C1.**

## 6. J2/J3 — SH 1.0 6-pin R/A SMD (XUNPU WAFER-SH1.0-6PWB, C3029345, 54.3 mm²)

| Rank | LCSC | MPN / maker | JLC stock / class | KiCad footprint | Area saved | Notes |
|---|---|---|---|---|---|---|
| **1** | **C160392** | **BM06B-SRSS-TB(LF)(SN)**, JST (genuine; vertical) | 40,742 / 35,514, Extended | `Connector_JST:JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical` | 51.0 mm² → 3.3 mm² per connector (courtyard), **plus the ~6 × 7 mm plug/cable zone in front of an R/A header** (≈ 40 mm² each, estimate) | 1 A/pin, 50 V; same pin 1–6 order and MP tabs.  Genuine JST is back in stock (r5 B4 forced the clone).  Needs vertical clearance for the plug and a cable bend above the top side.  The connector no longer has to sit at a board edge |
| 2 | C495540 | BM06B-SRSS-TBT(LF)(SN), JST | 46,092, Extended | same | same | Packaging variant of #1 |
| 3 | C3029336 | WAFER-SH1.0-6PLB, XUNPU (vertical clone) | 17,408, Extended | check its land against the JST footprint first (the R/A XUNPU needed a custom land) | same | Fallback |

**Recommend #1.**

## 7. R300/R400 — 22 Ω 1206 250 mW (C17958, Basic)

**Requirement** (DESIGN §3.3, r5 M2, round2_e N3, round16 N-05).
* P = (VM − 3.3 V) × IBK ≈ 70–100 mW continuous if a DRV8316 is never configured (buck left on).
* ~250 mW covers IBK ≤ 18 mA.
* Short on-pulses of up to ~0.6 A (8 W peak) before BUCK_CL is written.

A standard 0603 (100 mW) is **not** enough (that was r5 M2).  A pulse-rated 0603 with a 250 mW rating
matches the 1206.

| Rank | LCSC | MPN / maker | Package | Ratings | JLC stock / class | KiCad | Area saved (×2) | Risks |
|---|---|---|---|---|---|---|---|---|
| **1** | **C2074038** | **ESR03EZPJ220**, ROHM (anti-surge) | 0603 | 22 Ω ±5 %, **250 mW**, 150 V, pulse-rated series | 4,708 / 4,700, Extended | `Resistor_SMD:R_0603_1608Metric` | 10.3 → 4.3 mm²: **12.0 mm²** | Same rating in a smaller body, so it runs hotter per watt of copper.  ±5 % is irrelevant for RBK.  Give it normal pads with some copper |
| 2 | C2086076 | RCS060322R0JNEA, Vishay (anti-surge) | 0603 | 22 Ω ±5 %, 250 mW, 75 V | 1,865, Extended | same | 12.0 mm² | — |
| 3 | C441970 | ERJ-P06F22R0V, Panasonic (anti-surge) | 0805 | 22 Ω ±1 %, **500 mW** (better than the original) | 27,818, Extended | `R_0805_2012Metric` | 7.8 mm² | Safest: 2× the rating, smaller than 1206 |

**Recommend #1**, or #3 if you want margin over the original.

## 8. 10 µF 50 V X5R 1206 MLCCs (CL31A106KBHNNNE, C13585, Basic)

**The list, confirmed from the netlist/BOM, has 11 parts, not 8.**
* C302, C308, C309, C310 (U3 VM filter, L_VM) and C402, C408, C409, C410 (U4, R_VM).
* **plus C25, C26, C31** (VBAT, one per weapon half-bridge).

**Voltage.** **25 V is not acceptable.** TI's DRV8316 CVM rule ("≥ 10 µF … rated at least twice the
normal operating voltage", quoted in r2 D-13) needs ≥ 33.6 V at 16.8 V.  The TVS clamp reaches 32.4 V.
So the minimum is 35 V, and 50 V is preferred.

**Effective capacitance at 16.8 V (Samsung model data):**

| Part | Case | 16.8 V change | Effective per part |
|---|---|---|---|
| CL31A106KBHNNNE (current, C13585) | 1206 50 V X5R | −78 % | **2.2 µF** |
| CL21A106KBYQNNE (C2932476) | 0805 50 V X5R | −81 % | **1.9 µF** (−15 % vs current) |
| CL32A106KBJNNNE (C380537) | 1210 50 V X5R (2.5 mm tall) | −30 % | **7.0 µF** |

Murata GRM21BR61H106KE43L (C440198, the 0805 50 V **Basic** part, 1.8 M stock) is probably similar to
the Samsung 0805, but its curve is unverified (Murata's site blocked the fetch).

**(a) VM-filter caps C302/C308/C309/C310, C402/C408/C409/C410.**
* **0805 is not functionally identical.** It has 15 % less effective capacitance than the current
  parts.  In simulation, the worst in-environment bounce rises from 3.39 (current parts, realistic) to
  3.75 V/µs, and −40 °C from 4.15 to 4.64 V/µs.  **Do not swap these to 0805.**
* **Better option: 2 × CL32A106KBJNNNE 1210 per drive** in place of 4 × 1206 (C380537, Samsung, 37,099 /
  31,315 in stock, Extended; `Capacitor_SMD:C_1210_3225Metric`).  It gives ~14 µF per drive instead of
  ~8.8 µF real.  Simulated: 0 °C bounce 3.39 → **2.51 V/µs**, −40 °C 4.15 → **3.03**, min-UVLO
  re-close 3.23 → 2.40.  It also lowers the RC corner, so R302/R402 carry less of the drive's own
  ripple.
* **Area:** 4 × 10.6 = 42.4 → 2 × 14.7 = 29.4 mm², so **13 mm² per drive, 26 mm² total**, and 4 fewer
  placements.
* **Risks:**
  * 1210 on an unfused bus is a flex-crack short risk, so apply the §6.10 orientation/≥ 3 mm-from-holes
    rule (a soft-termination variant would be better; not checked for stock).
  * The ripple per part doubles, but at ~5 mΩ that is only milliwatts.
  * Update DESIGN §3.3, calcs §7 and `sim_hotplug.py` (`cvm`).
  * Verify the 1210 curve with a second source, as for the 1206.

**(b) Weapon local caps C25/C26/C31.**
* **0805 50 V is acceptable but not strictly equal:** −15 % effective capacitance per part.
* Hot-plug impact is negligible (2.26 → 2.28 V/µs, and 2.66 → 2.77 at −40 °C) because C1 dominates on
  VBAT.
* Their other role, local HF decoupling of each half-bridge, depends mainly on ESL and placement, which
  an 0805 matches or improves.
* **Options:** Murata GRM21BR61H106KE43L **C440198 (Basic)** or Samsung CL21A106KBYQNNE C2932476
  (curve verified; 208 k stock, presale 88 k).
* **Saves** 3 × 3.9 = 11.7 mm².  `sim_weapon_bridge.py` idealises the bridge MLCC as 20 µF either way.
* **Optional.**

## 9. Other oversized parts (low-risk only)

| Ref | Now | Proposed | LCSC / class / stock | Check | Saved |
|---|---|---|---|---|---|
| **R15** | 6.8 k 0805 125 mW (C17772) | 6.8 k 1 % 0603 100 mW, UNI-ROYAL 0603WAF6801T5E | **C23212, Basic**, 1.83 M | 41 mW at 16.8 V (41 % of rating).  At the 32.4 V clamp it is 154 mW, but that is brief and over the 0805's 125 mW rating too | 2.1 mm² |
| **C14** | 100 nF 100 V X7R 0805 (C28233) | 100 nF 100 V X7R 0603, Samsung CL10B104KC8NNNC (or YAGEO CC0603KRX7R0BB104, C113803) | C15725, Extended, 795 k | Keeps the 100 V rating (40–60 V ring).  Needs only ≥ 22 nF.  A smaller body is less flex-crack-prone across the unswitched pack | 2.4 mm² |
| **D10** | 1N4148W SOD-123 (C81598) | 1N4148WS SOD-323 | **C2128, Basic**, 2.27 M | 100 V (vs 75 V), 150 mA, 200 mW.  It only steers µA gate/Cdvdt currents.  At ~0.9 mm tall it could move to the bottom side (§6.13) | 4.7 mm² |
| D5 (optional) | B5819W SOD-123 | B5819WS SOD-323, MDD | C64886, Extended (preferred), 541 k | 40 V 1 A.  VC0 clamp and the C9 hot-plug pulse (≤ 168 mA).  Check VF at 0.1–0.2 A against the B5819W before adopting | 4.7 mm² |
| D4 (optional) | MMSZ5242B SOD-123 350 mW | MM3Z12VT1G SOD-323 300 mW, onsemi | C236177, Extended, 21 k | Vz 11.4–12.7 V vs 11.4–12.6 V (Vgs limit 15 V: OK).  **Lower Pd**: the gate clamp only sees transient current, but this is not strictly equal | 4.7 mm² |

**Keep as they are:**
* **C9** (4.7 µF 50 V X7R 1206).  An 0805 4.7 µF 50 V X5R keeps only ~0.94 µF at 16.8 V (Samsung
  CL21A475KBQNNN, −80 %), below TI's 1 µF minimum.
* **R6/R11** (100 Ω 0603).  DESIGN sized them for the plug-in and D5 pulses; they save only 2.6 mm²
  each.
* **D1** (SMBJ20A).  An SMA/SOD-123FL TVS has a lower surge rating (400/200 W vs 600 W).
* **R302/R402** (1 W, needed).

---

## Recommended set

| # | Change | Part (LCSC) | Class | Netlist / file impact | Area saved (courtyard) |
|---|---|---|---|---|---|
| 1 | U6 → WQFN-14 BQA | SN74LVC08ABQAR (C31971766) | Ext | add EP pad 15 = GND; `parts.py` footprint | 26.6 mm² |
| 2 | D2 → SOD-123W | PMEG4030ER,115 (C389355) [alt DSK34 C41029] | Ext | none (K = pad 1) | 14.6 mm² |
| 3 | L1 → 4.1 × 4.1 molded | ZEMS404030-220M (C49009291) [alt MTQH404030S220MBT] | Ext | none; update calcs §3 inductor row | 9.5 mm² |
| 4 | J4 → XH vertical | JST B5B-XH-A(LF)(SN) (C157991) | Ext | none | 91.6 mm² (+ edge approach zone) |
| 5 | C1 | **keep** EEHZK1V331P | — | — | 0 (37.8 possible, not recommended) |
| 6 | J2/J3 → SH vertical | JST BM06B-SRSS-TB(LF)(SN) (C160392) | Ext | none | 6.6 mm² (+ ~80 mm² of plug zones, estimate) |
| 7 | R300/R400 → 0603 250 mW | ROHM ESR03EZPJ220 (C2074038) | Ext | none | 12.0 mm² |
| 8a | VM filter 4 × 1206 → 2 × 1210 per drive | Samsung CL32A106KBJNNNE (C380537) | Ext | drop C309/C310/C409/C410; DESIGN §3.3, calcs §7, sim `cvm` | 26.0 mm² |
| 8b | C25/C26/C31 → 0805 50 V (optional) | Murata GRM21BR61H106KE43L (C440198) | **Basic** | none | 11.7 mm² |
| 9 | R15, C14, D10 → one size down | C23212 (Basic), C15725, C2128 (Basic) | — | none | 9.2 mm² |
| | **Total, recommended (1–4, 6, 7, 8a, 9)** | | | | **≈ 196 mm²** (+ ~11.7 with 8b, + connector mating zones) |

**Extended lines.** The set adds new Extended lines: C31971766, C389355, C49009291, C157991, C160392,
C2074038, C380537 and C15725.  J4 and J2/J3 were already Extended, so the net is ~+5 new lines.  At
$3 each, that is ~$15 per order in Economic PCBA.  Removing the SS34 and the 1206 22 Ω lines drops two
Basic lines.

## What I could not verify

* **Murata and TDK DC-bias curves** (their sites block scripted fetches).  All DC-bias numbers above are
  Samsung's typical model data.  The −78 % for the current 1206 part is the most consequential number in
  this proposal: confirm it before relying on either the "current design is fine" or the "1210 fixes
  it" reading.
* **DSK34's thermal-resistance mounting condition**, and the **Changjiang FTC322520S220 datasheet**
  (image-only PDF).
* **The ZE land-pattern letters** (A/B/C) were matched to the KiCad FTC404030S pads by the 4.1 mm outer
  span.  Check pad width (1.3 vs 1.4 mm) against the ZE drawing when drawing the footprint.
* **Vertical-connector heights** against the chassis lid (area and height are layout concerns;
  not blocking).
* **Stock** is a 2026-09-29 snapshot.  EEHZK1V221UP (967) and SN74LVC08ABQAR (2,984) are the thinnest.

Scratch files (not in the repo): `/tmp/v2parts/` holds the query helpers, the downloaded datasheets,
`sim_hotplug_c1.py` (the parameterised copy) and the `*.out` variant results summarised at the top.
