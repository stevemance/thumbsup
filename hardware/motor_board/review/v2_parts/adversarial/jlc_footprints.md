# Adversarial check: v2 part swaps vs JLCPCB assembly and footprints (2026-09-29)

Scope: `hardware/motor_board/review/v2_parts/proposal.md`. No repo files edited.
Evidence scripts and downloads: `/home/smance/.claude/jobs/35ed3eaa/tmp/advjlc/`
(`raw.py` = raw JLC API row, `pads.py` = pad dump of a .kicad_mod, `ee/lib.pretty` = JLC's own EasyEDA
footprints pulled with easyeda2kicad, `eXH.pdf` / `eSH.pdf` = JST catalogue pages).

Method:
* Every LCSC number was re-queried by exact code on the JLC SMT-library API (proposer's `stock.py`) and on
  LCSC detail (`q.py lcsc`).
* The footprints were compared pad by pad in three ways:
  * the stock KiCad footprint;
  * the manufacturer's land drawing;
  * JLC's own EasyEDA footprint. JLC's footprint is what their CPL preview and rotation are referenced to.

## 1. Identity / stock / class (JLC API, 2026-09-29)

All LCSC numbers map to exactly the named MPN.

| LCSC | MPN (maker) | JLC class | JLC stock / presale |
|---|---|---|---|
| C31971766 | SN74LVC08ABQAR (TI), WQFN-14 2.5x3 | Extended | 2,984 / 2,984 |
| C389355 | PMEG4030ER,115 (Nexperia), listed "SOD-123" | Extended | 12,169 / 12,097 |
| C41029 | DSK34 (MDD), SOD-123FL | Extended | 282,133 / 280,159 |
| C49009291 | ZEMS404030-220M (ZE) | Extended | 2,304 / 2,304 |
| C157991 | B5B-XH-A(LF)(SN) (JST), "Plugin" | Extended | 71,827 / 64,103 |
| C160392 | BM06B-SRSS-TB(LF)(SN) (JST) | Extended | 40,742 / 35,509 |
| C2074038 | ESR03EZPJ220 (ROHM), 250 mW 150 V | Extended | 4,708 / 4,700 |
| C380537 | CL32A106KBJNNNE (Samsung), 10 uF 50 V X5R 1210 | Extended | 37,099 / 31,315 |
| C23212 | 0603WAF6801T5E (Uniroyal), 100 mW 75 V | Basic | 1.83 M |
| C15725 | CL10B104KC8NNNC (Samsung), 100 nF 100 V X7R 0603 | Extended | 795 k |
| C2128 | 1N4148WS (JSCJ), 100 V 150 mA | Basic | 2.27 M |
| C440198 | GRM21BR61H106KE43L (Murata) | Basic | 1.80 M |
| C64886 | B5819WS (MDD) | Extended (preferred) | 541 k |
| C236177 | MM3Z12VT1G (onsemi) | Extended | 21 k |
| C495540 / C3029336 | BM06B-SRSS-TBT / XUNPU WAFER-SH1.0-6PLB | Extended | 46 k / 17 k |

The proposal's stock and class claims are correct.

## 2. Per-part verdicts

### U6 SN74LVC08ABQAR (C31971766): OK with condition

**TI BQA0014A land (SCAS283W, "Example board layout").**
* Signal pads are 0.25 x 0.6 at 0.5 pitch.
* The pad-centre spans are (2.3) x (2.8), so the pad centres are x = ±1.15 and y = ±1.4.
* The EP is 1.0 x 1.5.
* Pin 1 is on the short (top) side, left of centre; 2–6 run down the left side and 7/8 are on the bottom.

**JLC's EasyEDA footprint** (`WQFN-14_L3.0-W2.5-P0.50-TL-EP`) matches TI exactly: pads 0.25 x 0.6 at ±1.15 / ±1.4, EP 1.0 x 1.5, pin 1 at (−0.25, −1.4).

**KiCad footprint.** Use `Package_DFN_QFN:DHWQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm`. Its tags name it "Texas_BQA0014A".
* The proposed `DHVQFN-…` has identical pads, but it is the Nexperia SOT762 variant. The DHWQFN name is the TI-documented one.
* Its pads are 0.25 x 0.825 at ±1.188 / ±1.438, so they are longer (toe +0.15, heel +0.075) than TI's. That is acceptable (heel to EP 0.275 vs TI 0.35).
* The EP is 1.0 x 1.5, and the paste is one 0.81 x 1.21 window (65 %). TI shows 88 %. Both are fine for a logic part.

**Pin-1 orientation.** KiCad and JLC agree (pin 1 at −x, −y, on the short side), so the CPL rotation is 0°. There is no JLC correction for this package, but confirm it in the JLC DFM preview anyway.

**Capability.**
* The pad-to-pad gap is 0.25 mm, well over JLC's 0.15 SMD pad-to-pad rule and our custom DRU.
* The mask web is 0.25 mm at the board's 0 mask expansion. JLC's usual CAM expansion of about 0.05 per side still leaves 0.15, over the 0.1 mm dam minimum.
* The corner pads (1 vs 2) are 0.4 apart. The board already carries 0.5 mm QFNs (RGF0040E, QFN-20, RGZ0048), so there is no new capability risk.

**Conditions:**
1. **The EP (pad 15) has no pin on the current 14-pin `SN74LVC08APWR` symbol.**
   * If the symbol isn't extended, the pad ends up net-less and floats. TI allows that, but the proposal says to tie it to GND.
   * To tie it, add pin 15 to the symbol/pin map (and to `parts.UNITS` power group {7, 14, 15}).
   * Also update `STOCK_EASYEDA_REF` with `WQFN-14_L3.0-W2.5-P0.50-TL-EP…` so check_lib compares the pad arrangement.
2. **Stock is 2,984 in one lot, and the part is Extended.** Fine for prototypes. There is no second source in this package with real stock (the Nexperia BQ has 3).

### D2 PMEG4030ER (C389355): OK

**Nexperia reflow footprint (Fig. 15, sod123w_fr).** Lands are 1.2 x 1.2 at 2.8 mm pitch (paste 1.1, resist 1.4).

**KiCad `Diode_SMD:Nexperia_CFP3_SOD-123W`.** Pads 1.2 x 1.2 at ±1.4: an **exact match**.
* The package is 3.3–3.7 long overall, which is inside the 4.0 land span.
* Pad 1 = K, and the KiCad `Diode:SS34` symbol also has pin 1 = K, so the netlist is unchanged.

**Do not use `D_SOD-123F`** for this part. Its pads are 1.1 x 1.1: slightly undersized for the CFP3's wide, flat tab.

**JLC.**
* JLC lists the package as "SOD-123". Its EasyEDA footprint (`SOD-123_L2.6-W1.7-LS3.5-RD`) is a generic 0.9 x 1.0 land at ±1.69, which JLC doesn't use for fabrication.
* Pad 1 (K) is at −x in both, so the rotation is 0°.
* JLC's CPL check is by cathode band. Make sure the silk cathode bar is on pad 1.

**Thermal note** (not a JLC issue). The Rth(j-a) of 130 K/W requires 1 cm² of **cathode** copper (datasheet note [3]). The cathode is the SW node, which you want small. With the minimum SW pad, use the "standard footprint" 220 K/W figure. At 0.6 W that gives Tj ≈ 50 + 132 ≈ 182 °C, over 150 °C in a sustained +5V short.
* The proposal's "give the anode a GND pour" does not help this part. Its heat path is the cathode tab ("soldering point of cathode tab", note [5]).
* This is outside the JLC scope, but it contradicts the proposal's Tj claim. It needs the short-circuit duration argument (buck thermal shutdown), not the 130 K/W figure.

### D2 fallback DSK34 (C41029): OK with condition

**MDD's suggested pad layout (datasheet p.3).**
* A = 1.2 (pad height), B = 1.2 (pad width), C = 3.2 (centre–centre), D = 2.0 (gap), E = 4.4 (outer).
* The package is 3.45–4.0 long overall, with leads 0.8–1.2 wide and 0.3–1.0 long.

**KiCad `D_SOD-123F`.** Pads 1.1 x 1.1 at ±1.4 (outer 3.9, gap 1.7). That is **smaller and 0.4 mm tighter than MDD's land.** At maximum package length (4.0 mm) the lead toes overhang the pads.
* **Condition: use a 1.2 x 1.2 land at ±1.6** (MDD's own values), or `Nexperia_CFP3_SOD-123W` as a compromise (1.2 x 1.2 at ±1.4, still 0.4 mm short of MDD's outer span).
* The proposal's area figure (14.4 mm²) then grows by about 1.5 mm².
* JLC's footprint `SOD-123_L2.8-W1.8-LS3.7-RD` is 0.95 x 1.15 at ±1.69, with pad 1 at −x, so the rotation is 0°.

### L1 ZEMS404030-220M (C49009291): OK (proposal's pad concern is a misreading) + one JLC caveat

**ZE land drawing (datasheet p.3).**
* **A = 4.10 is the overall span, B = 1.30 is the gap between the pads, and C = 4.10 is the pad length.** B is not the pad width.
* So each pad is (4.1 − 1.3) / 2 = **1.4 mm wide**, at centres ±1.35.

**KiCad `Inductor_SMD:L_Changjiang_FTC404030S`.** Pads 1.4 x 4.1 at ±1.35: an **exact match**. The "1.3 vs 1.4 mm pad" concern in the proposal does not exist.

The part is unpolarised and symmetric (no dot orientation needed for a buck), so the rotation doesn't matter.

**JLC caveat.**
* JLC/EasyEDA has **no footprint or symbol data for C49009291**. easyeda2kicad got "Failed to fetch data from EasyEDA API" twice.
* JLC's DFM preview will therefore show no land overlay. They may ask for a manual placement confirmation or add a review delay.
* The alternate MTQH404030S220MBT (C51883186) *does* have one: `IND-SMD_L4.1-W4.1_FTC404020S`, pads 1.55 x 4.4 at ±1.42, a similar geometry.
* If avoiding JLC queries matters, use the MetalLions part; the footprint is the same.

### J4 JST B5B-XH-A (C157991): OK with conditions (THT)

**JST XH catalogue ("PC board layout", top entry, 3+ circuits).**
* Holes are **Ø0.9 +0.1/−0**, pitch 2.5 ±0.05. There is no boss on B5B-XH-A (the boss version is -AM).
* **The assembled height is 9.8 mm** (header 7.0).

**KiCad `Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical`.** Drill 0.95, pads 1.7 x 1.95, pitch 2.5. This matches JST (mid-tolerance) and is the same drill as the current S5B footprint.
* The post is 0.64 square, so its diagonal is 0.905. JLC's finished-PTH tolerance is +0.13/−0.08, so a 0.95 hole can finish at 0.87 and be a tight press.
* Consider a 1.0 mm drill (JST's upper limit) for hand soldering. This is optional; it is the same risk as today.

**JLC's EasyEDA footprint for C157991 is wrong/different.**
* **The pitch is 2.54** (not 2.5).
* The drill is 1.2.
* **Pin 1 is at +x**, and the origin is at the body centre.
* KiCad's footprint has pin 1 at x = 0 (its origin, the left end).

If JLC does the THT assembly, the KiCad CPL needs:
* a **180° rotation correction**, and
* a **+5 mm X origin offset** (KiCad origin = pin 1, JLC = centre). kicad-jlcpcb-tools has per-part rotation/offset overrides.

**Rotating an XH header 180° is not harmless.** The shroud's polarising wall would force the balance plug in reversed, putting B− on pin 5. Put an unambiguous pin-1 silk mark on the board and check the JLC preview against the housing drawing.

**Assembly.** THT via JLC's THT service (standard PCBA; confirm at order that the part is offered for THT) or hand-solder, as now.

**Height.** 9.8 mm mated plus the wire bend, which is more than the proposal's "~7 mm" (that is the header alone). This is a layout/lid item, not a blocker.

### J2/J3 JST BM06B-SRSS-TB (C160392): OK with CPL condition

**JST SH catalogue ("PC board layout", top entry), viewed from the mounting surface.**
* The two tabs are 1.2 x 1.8 on the top edge, and the signal pads are 0.6 wide x (4.2 − 2.65 = 1.55) on the bottom edge.
* Pin pitch is 1.0. The tab centres are 0.7 + 0.6 = 1.3 outside pins 1/N, i.e. ±3.8 for 6-way.
* The overall land depth is 4.2. **No. 1 circuit is on the left, with the tabs up.**

**KiCad `JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical`.**
* Signal pads 0.6 x 1.55 at y = +1.325, with pins 1→6 at x = −2.5 … +2.5 (pin 1 left).
* MP 1.2 x 1.8 at (±3.8, −1.2), so the tabs are up.
* This **exactly matches JST, including pin-1 side and no mirroring**.
* The MP pads are named "MP", which is compatible with the `Conn_01x06_MountingPin` symbol, as today.

**JLC's EasyEDA footprint** (`CONN-SMD-6P-P1.00_BM06B-SRSS-TB-LF-SN`) is the same land **rotated 180°**: signal row at y = −1.26, pin 1 at x = +2.5, tabs (numbered 7/8) at y = +1.26.
* It is a pure rotation (not a mirror), so it is consistent.
* **The CPL needs a 180° rotation correction** for J2/J3, or JLC's preview will show the part flipped. A flipped part would reverse the 6 signals.
* This is the classic JST-SH pitfall. Check the preview's pin-1 triangle against the silk.

**Capability.** The signal gap is 0.4 mm. The tab-to-pin-1/6 spacing is ≥ 0.4 in x and the pads are in different rows. No issue.

**Other notes.**
* The vertical body is 4.25 tall.
* Pin numbering follows the housing, so the cable pin-1-to-pin-1 mapping is unchanged vs the R/A part. Only the routing and the cable exit direction change.

### R300/R400 ROHM ESR03EZPJ220 (C2074038): OK

LCSC confirms 22 Ω ±5 %, 250 mW, 150 V, −55…+155 °C.

KiCad `R_0603_1608Metric` (0.8 x 0.95 at ±0.825) vs JLC's generic R0603 (0.81 x 0.86 at ±0.75): the same arrangement. It is non-polar, so rotation doesn't matter.

Condition (thermal, not JLC): ROHM's 250 mW rating assumes their test-board land and copper. Keep ≥ ~0.3 mm traces or small pours on both pads, as the proposal says.

### C380537 CL32A106KBJNNNE: OK

LCSC confirms 10 uF ±10 % 50 V X5R 1210.

KiCad `C_1210_3225Metric` (1.15 x 2.7 at ±1.475) vs JLC's C1210 (1.635 x 2.7 at ±1.52): both are standard 1210 lands. KiCad's is the IPC nominal one.

The "J" thickness code is 2.5 mm; place it on the top side or check the bottom-side stack clearance. The flex-crack placement rule (proposal §8) stands.

### R15 C23212: OK

6.8 k 1 % 100 mW, **75 V rating**. At the 32.4 V clamp that is 154 mW, over rating (the proposal already notes this is brief). Footprint `R_0603_1608Metric`.

### C14 C15725: OK

100 nF 100 V X7R 0603, Extended (not Basic; the proposal says so correctly). Footprint `C_0603_1608Metric`.

### D10 C2128 1N4148WS: OK

JSCJ, 100 V 150 mA 200 mW (the proposal's 100 V is correct).

KiCad `D_SOD-323` has pads 0.6 x 0.45 at ±1.05. JLC's `SOD-323_L1.8-W1.3-LS2.5-RD` is 1.0 x 0.7 at ±1.17. Pad 1 = K at −x in both, so the rotation is 0°.
* KiCad's land is small but standard.
* If you want more reflow margin, `D_SOD-323_HandSoldering` or a 0.8 x 0.6 land is closer to what JLC's library uses. This is optional.

### Optional: Murata C440198 (0805 10 uF 50 V, Basic): OK

KiCad `C_0805_2012Metric` vs JLC C0805 is a standard match. The DC-bias concern is electrical (proposal §8b), not a JLC issue.

### Optional: D5 B5819WS C64886 / D4 MM3Z12VT1G C236177 (SOD-323): OK

Both are SOD-323 with pad 1 = K. Same footprint and rotation notes as D10.

* **B5819WS (MDD):** the LCSC params give Tj max **125 °C** and IFSM 25 A.
* **MM3Z12VT1G:** Vz 11.4–12.7 V, 300 mW, Tj 150 °C.

## 3. CPL / rotation summary

These come from comparing each KiCad footprint to JLC's own EasyEDA footprint.

| Ref | KiCad fp | JLC fp orientation vs KiCad | Action |
|---|---|---|---|
| U6 | DHWQFN-14 (BQA) | same (pin 1 −x, −y) | 0°; verify preview |
| D2 | Nexperia_CFP3_SOD-123W | same (K at −x) | 0° |
| D2 alt | 1.2x1.2 @ ±1.6 custom / CFP3 | same | 0° |
| L1 | L_Changjiang_FTC404030S | no JLC footprint (ZE); symmetric | none; expect a DFM query |
| J4 | JST_XH_B5B-XH-A Vertical | pin 1 at +x, origin at body centre, 2.54 pitch drawing | **180° + 5 mm X offset** if JLC places it; pin-1 silk |
| J2/J3 | JST_SH_BM06B-SRSS-TB Vertical | rotated 180° | **180°** |
| D10/D4/D5 | D_SOD-323 | same | 0° |
| R/C 0603/0805/1210 | stock | symmetric | none |

## 4. JLC 4-layer capability (SMD pad-to-pad 0.15, mask dam 0.1)

Only U6 (0.5 mm pitch) and J2/J3 (1.0 mm) are fine-pitch.
* **U6:** gap 0.25, web 0.25 (0.15 after JLC's typical expansion).
* **J2/J3:** gap 0.4.

Both pass. Nothing in the set is under 0.5 mm pitch; the rejected X1-DFN1010 at 0.35 mm would have been the only risk.

## 5. Findings the proposal got wrong or missed

1. **The ZE land "1.3 vs 1.4 mm" worry is unfounded.** B = 1.30 is the gap, and the FTC404030S footprint matches exactly.
2. **Use `DHWQFN-14-1EP_2.5x3mm…`**, KiCad's BQA0014A-tagged footprint, rather than the DHVQFN (Nexperia) name. The pads are identical. The U6 symbol/pin map needs pin 15.
3. **`D_SOD-123F` is undersized for the DSK34.** MDD specifies 1.2 x 1.2 at 3.2 mm pitch.
4. **PMEG4030ER thermal claim.** The 130 K/W figure needs 1 cm² of *cathode* (SW node) copper, and an anode GND pour does not help this part. With a small SW node use ~220 K/W. Rely on the short-circuit duration, not on Tj staying under 150 °C.
5. **J2/J3 and J4 need 180° CPL corrections at JLC.** J4 also needs a centre offset, and JLC's own XH footprint is drawn at 2.54 pitch. A 180° error on either connector reverses the pinout: the balance leads on J4, or the 6 signals on J2/J3.
6. **J4's mated height is 9.8 mm (JST)**, not ~7 mm.
7. **C49009291 has no JLC/EasyEDA footprint data**, which will likely trigger a JLC query. The MetalLions alternate has one.
