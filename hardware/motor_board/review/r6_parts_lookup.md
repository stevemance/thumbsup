# R6 — JLCPCB / LCSC parts lookup (motor board BOM revision)

Queried 2026-09-23 via the LCSC product-detail JSON (`wmsc.lcsc.com/ftps/wm/product/detail`) and the JLC SMT-library search API (`selectSmtComponentList/v2`), one request at a time with ~2 s gaps. Class: **Basic** = JLC `componentLibraryType=base`; **Extended** = `expand`; **Preferred** = Extended with `preferredComponentFlag=true` (no extended-part loading fee). "JLC presale" = `canPresaleNumber`. Stock is a snapshot and changes daily. Ratings come from JLC/LCSC parameter fields. Where a datasheet was checked, the datasheet value is quoted and marked **(DS)**.

## A. Proposed replacements: confirmation

| # | C-no | MPN | Maker | Package | Key ratings | Class | JLC stock | JLC presale | LCSC stock | Verdict | Links |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C543035 | DRV8323RHRGZR | TI | VQFN-48-EP 7x7 | 6–60 V 3-ph gate driver, 1 A src / 2 A sink, SPI (H), 3 CSAs (R) | Extended | 203 | 186 | 203 | OK but LOW stock (203) — buy/reserve early | [LCSC](https://www.lcsc.com/product-detail/C543035.html) / [JLC](https://jlcpcb.com/partdetail/C543035) |
| 2 | C5447274 | DRV8316CRRGFR | TI | VQFN-40 (RGF, 7x5) | 3-ph integrated driver, 8 A peak, 95 mΩ, SPI | Extended | 2,928 | 2,886 | 2,928 | OK | [LCSC](https://www.lcsc.com/product-detail/C5447274.html) / [JLC](https://jlcpcb.com/partdetail/C5447274) |
| 3 | C2876522 | INA239AIDGSR | TI | VSSOP-10 0.5 mm | 85 V CM, ±163.84 mV FS, SPI, 2.7–5.5 V | Extended | 111 | 75 | 111 | OK but LOW stock (111) | [LCSC](https://www.lcsc.com/product-detail/C2876522.html) / [JLC](https://jlcpcb.com/partdetail/C2876522) |
| 4 | C278516 | EEHZK1V331P | Panasonic | SMD D10 x L10.2 | 330 µF 35 V hybrid polymer; ESR 20 mΩ (100 kHz, 20 °C); ripple 2800 mA rms (100 kHz/125 °C, ZK datasheet case G); 4000 h @125 °C | Extended | 6,558 | 6,515 | 6,548 | OK (LCSC field '420 mA@100Hz' is not the datasheet 100 kHz figure; datasheet says 2800 mA) | [LCSC](https://www.lcsc.com/product-detail/C278516.html) / [JLC](https://jlcpcb.com/partdetail/C278516) |
| 5 | C377773 | CL21A225KBQNNNE | Samsung | 0805 | 2.2 µF ±10% 50 V X5R | Basic | 705,382 | 577,504 | 220,110 | OK | [LCSC](https://www.lcsc.com/product-detail/C377773.html) / [JLC](https://jlcpcb.com/partdetail/C377773) |
| 6 | C17958 | 1206W4F220JT5E | UNI-ROYAL | 1206 | 22 Ω ±1% 250 mW 200 V 100 ppm | Basic | 909,259 | 844,029 | 670,600 | OK (MPN spelled ...F220JT5E, value is 22 Ω 1%) | [LCSC](https://www.lcsc.com/product-detail/C17958.html) / [JLC](https://jlcpcb.com/partdetail/C17958) |
| 7 | C137735 | RC0603FR-07390KL | YAGEO | 0603 | 390 kΩ ±1% 100 mW 75 V | Extended | 15,940 | 9,179 | 2,500 | OK (Extended). No 390k 0603 Basic checked | [LCSC](https://www.lcsc.com/product-detail/C137735.html) / [JLC](https://jlcpcb.com/partdetail/C137735) |
| 8 | C19666 | CL10A475KO8NNNC | Samsung | 0603 | 4.7 µF ±10% 16 V X5R | Basic | 2,787,403 | 2,315,180 | 1,035,450 | OK | [LCSC](https://www.lcsc.com/product-detail/C19666.html) / [JLC](https://jlcpcb.com/partdetail/C19666) |
| 9a | C167971 | FNR5040S220MT | cjiang (Changjiang Micro) | SMD 5x5 (x4.0) | 22 µH ±20%; DCR 0.129 typ / 0.168 max Ω; Isat 1.60 (guar.) / 1.80 typ A; Irms 1.50/1.60 A (datasheet p.13) | Extended | 24,474 | 24,032 | 24,470 | OK. Note LCSC 'Current rating 1.6 A' = Isat guaranteed column | [LCSC](https://www.lcsc.com/product-detail/C167971.html) / [JLC](https://jlcpcb.com/partdetail/C167971) |
| 9b | C843299 | FHD4020S-220MT | cjiang | SMD 4x4 | 22 µH ±20%; DCR 415 mΩ; Isat 1.5 A; rated 1.1 A (LCSC params; datasheet not cross-checked) | Extended | 6,106 | 6,023 | 6,100 | OK, much higher DCR than FNR5040S. No KiCad FHD footprint in stock lib | [LCSC](https://www.lcsc.com/product-detail/C843299.html) / [JLC](https://jlcpcb.com/partdetail/C843299) |
| 10 | C8678 | SS34 | MDD (Microdiode) | SMA (DO-214AC) | 40 V 3 A Schottky; VF 0.55 V @3 A; IR 0.5 mA @40 V 25 °C (5 mA @125 °C); IFSM 80 A | Basic | 4,617,687 | 4,463,996 | 4,089,940 | YES — SS34, 40 V 3 A, SMA, JLC Basic | [LCSC](https://www.lcsc.com/product-detail/C8678.html) / [JLC](https://jlcpcb.com/partdetail/C8678) |
| 11a | C3029345 | WAFER-SH1.0-6PWB | XUNPU | SMD right-angle, P1.0 | 1x6, 1 A 50 V, LCP, 2 solder tabs ('Auxiliary Solder Pin') | Extended | 30,553 | 29,533 | 30,550 | Right-angle (horizontal, 卧贴) SMD with 2 tabs: YES. Land differs from JST — see below | [LCSC](https://www.lcsc.com/product-detail/C3029345.html) / [JLC](https://jlcpcb.com/partdetail/C3029345) |
| 11b | C53055322 | SH1.0mm-6P-WT | LXWCONN | SMD right-angle, P1.0 | 1x6, 1 A 50 V, LCP, phosphor bronze, 2 tabs | Extended | 28,835 | 28,794 | 28,830 | Right-angle SMD with 2 tabs: YES. Land differs from JST — see below | [LCSC](https://www.lcsc.com/product-detail/C53055322.html) / [JLC](https://jlcpcb.com/partdetail/C53055322) |

### A11. SH 1.0 mm 6-pin right-angle clones compared with JST SM06B-SRSS-TB

Reference: KiCad `Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal` (follows JST's recommended land). Signal pads are 0.6 x 1.55 mm at y=-2.0 with 1.0 mm pitch (x = -2.5 … +2.5). The two MP tabs are 1.2 x 1.8 mm at x = ±3.8, y = +1.875. From the top of the signal pads to the bottom of the tabs is 5.55 mm.

| Item | JST SM06B (KiCad fp) | XUNPU WAFER-SH1.0-6PWB (DS drawing) | LXWCONN SH1.0mm-6P-WT (DS drawing) |
|---|---|---|---|
| Orientation | side entry, SMD | right-angle SMD (3-D view: leads exit rear, 2 tabs) | right-angle SMD ("卧贴"), 2 tabs (焊片 x2) |
| Pitch / pin span | 1.0 / 5.0 | 1.00 / 5.00 | 1.0 / 5.0 (A) |
| Signal pad (w x l) | 0.6 x 1.55 | 0.50 x 1.70 | 0.7 x 1.3 |
| Tab pad (w x l) | 1.2 x 1.8 | 1.20 x 2.50 | 0.8 x 1.95 |
| Tab centre, x | ±3.80 | ±3.60 (inner edge 0.50 beyond pin-6 centre, width 1.20) | ±3.6 (1.1 from pin-1 centre to tab centre) |
| Pad top → tab bottom | 5.55 | 5.50 | 1.3 + 4.3 = 5.6 |
| Body (B/C) | B 8.0 (JST table) | B 8.35 / C 6.60, depth 5.05, height 3.15 | C 8.4 / B 6.6, depth 5.0, height 3.2 |
| Pin-1 marking | JST: circuit 1 marked | **not marked on drawing — UNVERIFIED** | ① is the part-number callout (pin), not pin 1 — **UNVERIFIED** |

Assessment (read off the drawings; not a measured fit). Both clones are true right-angle SMD headers with two tabs, and their pitch and overall depth match the JST part. Their tabs sit about 0.2 mm further inboard (±3.6 vs ±3.8). The metal tab (drawn as the red outline on the XUNPU sheet, centred at x=±3.6) still lands inside the JST 1.2 mm tab pad (x 3.2–4.4), so on the JST footprint it would solder but off-centre. If you use a clone, make its footprint from the vendor land pattern. Pin-1 end: both drawings are symmetric and do not name pin 1. Before committing a cable, check which end mates with pin 1 of a JST SHR-06V housing.

KiCad has no stock footprint for either clone.

## B. New parts: candidates (Basic first, then in-stock Extended)

| # | Need | Pick | C-no | MPN | Maker | Package | Key ratings | Class | JLC stock | JLC presale | LCSC stock | Links |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | 220 nF 50 V X7R 0603 | 1 | C64705 | CL10B224KB8NNNC | Samsung | 0603 | 220 nF ±10% 50 V X7R | Extended | 329,038 | 300,997 | 329,000 | [LCSC](https://www.lcsc.com/product-detail/C64705.html) / [JLC](https://jlcpcb.com/partdetail/C64705) |
| 12 |  | 2 | C344195 | TCC0603X7R224K500CT | CCTC | 0603 | 220 nF ±10% 50 V X7R | Extended | 1,318,611 | 1,307,137 | 1,299,450 | [LCSC](https://www.lcsc.com/product-detail/C344195.html) / [JLC](https://jlcpcb.com/partdetail/C344195) |
| 12 |  | (Basic alt) | C5378 | CL21B224KBFNNNE | Samsung | **0805** | 220 nF 50 V X7R. Basic, but 0805. The only Basic 220 nF 0603 is C21120, which is 25 V | Basic | 683,075 | — | not queried | [LCSC](https://www.lcsc.com/product-detail/C5378.html) / [JLC](https://jlcpcb.com/partdetail/C5378) |
| 13 | 1 nF 50 V 0402 | 1 | C1523 | 0402B102K500NT | FH (Fenghua) | 0402 | 1 nF ±10% 50 V X7R | Basic | 3,819,021 | 3,343,817 | 2,994,400 | [LCSC](https://www.lcsc.com/product-detail/C1523.html) / [JLC](https://jlcpcb.com/partdetail/C1523) |
| 13 |  | 2 (C0G) | C53547 | 0402CG102J500NT | FH (Fenghua) | 0402 | 1 nF ±5% 50 V C0G | Extended | 203,530 | 193,517 | 183,850 | [LCSC](https://www.lcsc.com/product-detail/C53547.html) / [JLC](https://jlcpcb.com/partdetail/C53547) |
| 14 | 47 kΩ 1% 0402 | 1 | C25792 | 0402WGF4702TCE | UNI-ROYAL | 0402 | 47 kΩ ±1% 62.5 mW | Basic | 5,820,857 | 5,477,580 | 4,578,600 | [LCSC](https://www.lcsc.com/product-detail/C25792.html) / [JLC](https://jlcpcb.com/partdetail/C25792) |
| 14 |  | 2 | C93943 | RC0402FR-0747KL | YAGEO | 0402 | 47 kΩ ±1% 62.5 mW | Extended | 5,433,098 | 5,379,191 | 5,331,100 | [LCSC](https://www.lcsc.com/product-detail/C93943.html) / [JLC](https://jlcpcb.com/partdetail/C93943) |
| 14 | 75 kΩ 1% 0402 | 1 | C25798 | 0402WGF7502TCE | UNI-ROYAL | 0402 | 75 kΩ ±1% 62.5 mW | **Preferred** (no Basic 75k 0402) | 57,276 | 19,176 | 0 (LCSC side) | [LCSC](https://www.lcsc.com/product-detail/C25798.html) / [JLC](https://jlcpcb.com/partdetail/C25798) |
| 14 |  | 2 | C140129 | RC-02K7502FT | FH (Fenghua) | 0402 | 75 kΩ ±1% 62.5 mW | Extended | 211,845 | 197,119 | 182,900 | [LCSC](https://www.lcsc.com/product-detail/C140129.html) / [JLC](https://jlcpcb.com/partdetail/C140129) |
| 14 | 18 kΩ 1% 0402 | 1 | C25762 | 0402WGF1802TCE | UNI-ROYAL | 0402 | 18 kΩ ±1% 62.5 mW | **Preferred** (no Basic 18k 0402) | 592,217 | 535,027 | 480,600 | [LCSC](https://www.lcsc.com/product-detail/C25762.html) / [JLC](https://jlcpcb.com/partdetail/C25762) |
| 14 |  | 2 | C138044 | RC0402FR-0718KL | YAGEO | 0402 | 18 kΩ ±1% 62.5 mW | Extended | 1,015,164 | 1,010,100 | 1,006,200 | [LCSC](https://www.lcsc.com/product-detail/C138044.html) / [JLC](https://jlcpcb.com/partdetail/C138044) |
| 14 | 4.7 kΩ 1% 0402 | 1 | C25900 | 0402WGF4701TCE | UNI-ROYAL | 0402 | 4.7 kΩ ±1% 62.5 mW | Basic | 16,283,389 | 15,075,986 | 11,890,700 | [LCSC](https://www.lcsc.com/product-detail/C25900.html) / [JLC](https://jlcpcb.com/partdetail/C25900) |
| 14 |  | 2 | C105871 | RC0402FR-074K7L | YAGEO | 0402 | 4.7 kΩ ±1% 62.5 mW | Extended | 8,156,278 | 8,025,339 | 7,889,800 | [LCSC](https://www.lcsc.com/product-detail/C105871.html) / [JLC](https://jlcpcb.com/partdetail/C105871) |
| 14b | 330 Ω 1% 0402 (added) | 1 | C25104 | 0402WGF3300TCE | UNI-ROYAL | 0402 | 330 Ω ±1% 62.5 mW | Basic | 1,346,266 | 1,160,765 | not queried | [LCSC](https://www.lcsc.com/product-detail/C25104.html) / [JLC](https://jlcpcb.com/partdetail/C25104) |
| 14b |  | 2 | C105875 | RC0402FR-07330RL | YAGEO | 0402 | 330 Ω ±1% 62.5 mW | Extended | 2,362,227 | 2,335,648 | not queried | [LCSC](https://www.lcsc.com/product-detail/C105875.html) / [JLC](https://jlcpcb.com/partdetail/C105875) |
| 14c | 22 pF C0G 50 V 0402 (added) | 1 | C1555 | 0402CG220J500NT | FH (Fenghua) | 0402 | 22 pF ±5% 50 V C0G | Basic | 1,742,113 | 1,520,663 | not queried | [LCSC](https://www.lcsc.com/product-detail/C1555.html) / [JLC](https://jlcpcb.com/partdetail/C1555) |
| 14c |  | 2 | C106203 | CC0402JRNPO9BN220 | YAGEO | 0402 | 22 pF ±5% 50 V NP0 | Extended | 3,013,189 | 2,984,716 | not queried | [LCSC](https://www.lcsc.com/product-detail/C106203.html) / [JLC](https://jlcpcb.com/partdetail/C106203) |
| 15 | Triple Schmitt buffer | 1 (DCU) | C68245 | SN74LVC3G17DCUR | TI | VSSOP-8 2.3x2 P0.5 (DCU) | VCC 1.65–5.5 V; **inputs accept 5.5 V (DS, SCES470F)**; ±32 mA; −40…125 °C | Extended | 3,335 | 3,241 | 3,335 | [LCSC](https://www.lcsc.com/product-detail/C68245.html) / [JLC](https://jlcpcb.com/partdetail/C68245) |
| 15 |  | 2 (DCT, same pinout) | C18213 | SN74LVC3G17DCTR | TI | SSOP-8 2.95x2.8 P0.65 (DCT; LCSC calls it 'MSOP-8-2.8mm') | same die/datasheet SCES470; DCT and DCU pinouts identical (DS pin table); LCSC temp field −40…85 °C | Extended | 7,218 | 7,106 | 7,218 | [LCSC](https://www.lcsc.com/product-detail/C18213.html) / [JLC](https://jlcpcb.com/partdetail/C18213) |
| 16 | Quad 2-in AND, TSSOP-14 (PW) | 1 | C465737 | SN74LVC08APWR | TI | TSSOP-14 4.4x5 (PW) | VCC 1.65–3.6 V; **inputs accept 5.5 V (DS, SCAS283T)**; ±24 mA | Extended | 35,282 | 35,226 | 35,190 | [LCSC](https://www.lcsc.com/product-detail/C465737.html) / [JLC](https://jlcpcb.com/partdetail/C465737) |
| 16 |  | 2 | C6053 | 74LVC08APW,118 | Nexperia | TSSOP-14 (PW) | VCC 1.2–3.6 V; overvoltage-tolerant inputs (5 V); ±24 mA | Extended | 17,470 | 17,445 | 17,465 | [LCSC](https://www.lcsc.com/product-detail/C6053.html) / [JLC](https://jlcpcb.com/partdetail/C6053) |
| 16 |  | (smaller, low stock) | C31971766 | SN74LVC08ABQAR | TI | WQFN-14 2.5x3 (BQA) | same function; no params listed | Extended | 2,990 | 2,990 | 2,990 | [LCSC](https://www.lcsc.com/product-detail/C31971766.html) / [JLC](https://jlcpcb.com/partdetail/C31971766) |
| 17 | PTC 0603, ~100 mA | 1 | C207010 | 0603L010YR | Littelfuse | 0603 | Ihold 0.10 A, Itrip 0.30 A, Vmax 15 V, Imax 40 A; **Rmin 0.90 Ω, R1max 6.0 Ω**; trip ≤1.0 s @0.5 A (DS) | Extended | 13,295 | 13,200 | 13,295 | [LCSC](https://www.lcsc.com/product-detail/C207010.html) / [JLC](https://jlcpcb.com/partdetail/C207010) |
| 17 |  | 2 | C70047 | SMD0603-010 | TECHFUSE | 0603 | Ihold 100 mA, Itrip 300 mA, 15 V; R 0.9 Ω / R1max 6 Ω (LCSC params) | Extended | 16,202 | 15,990 | 15,900 | [LCSC](https://www.lcsc.com/product-detail/C70047.html) / [JLC](https://jlcpcb.com/partdetail/C70047) |
| 17 | PTC 0805 alt | 3 | C7472554 | 0805L010/24XR | LUTE | 0805 | Ihold 100 mA, Itrip 300 mA, 24 V; R 0.75 Ω / R1max 6 Ω (LCSC) | Extended | 122,819 | 122,692 | 122,600 | [LCSC](https://www.lcsc.com/product-detail/C7472554.html) / [JLC](https://jlcpcb.com/partdetail/C7472554) |
| 17 | PTC 50 mA alt | 4 | C70046 | SMD0603-005-24V | TECHFUSE | 0603 | Ihold 50 mA, Itrip 200 mA, 24 V; R 2 Ω / R1max 25 Ω (LCSC) | Extended | 75,828 | 74,738 | 74,420 | [LCSC](https://www.lcsc.com/product-detail/C70046.html) / [JLC](https://jlcpcb.com/partdetail/C70046) |
| 17 | Current-limited load switch | 1 | C47507 | TPS22945DCKR | TI | SC-70-5 (DCK) | 1.62–5.5 V; 400 mΩ; **ILIM 100 min / 150 typ / 200 max mA** (DS); 10 ms blanking then 80 ms auto-restart; ON active-high; OC open-drain; pins 1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN (DS) | Extended | 10,164 | 10,151 | 10,158 | [LCSC](https://www.lcsc.com/product-detail/C47507.html) / [JLC](https://jlcpcb.com/partdetail/C47507) |
| 17 |  | 2 (same pinout) | C200357 | TPS22944DCKR | TI | SC-70-5 (DCK) | Same datasheet, same pinout, same 100–200 mA limit, active-high. Differences: **no blanking time and no auto-restart** (DS device table) | Extended | 82 | 80 | not queried | [LCSC](https://www.lcsc.com/product-detail/C200357.html) / [JLC](https://jlcpcb.com/partdetail/C200357) |
| 18 | Small-signal Schottky | 1 | C124205 | BAT54WS-7-F | Diodes Inc | SOD-323 | 30 V; IO 100 mA avg, IF 200 mA cont. (DS), VF 1 V@100 mA, IR 2 µA@25 V | Extended | 76,868 | 76,306 | 76,660 | [LCSC](https://www.lcsc.com/product-detail/C124205.html) / [JLC](https://jlcpcb.com/partdetail/C124205) |
| 18 |  | 2 | C3040452 | BAT54WS | FUXINSEMI | SOD-323 | 30 V 200 mA, VF 1 V@100 mA, IR 2 µA | Extended | 121,405 | 120,866 | 121,400 | [LCSC](https://www.lcsc.com/product-detail/C3040452.html) / [JLC](https://jlcpcb.com/partdetail/C3040452) |
| 18 |  | (Basic alt, NOT low-leak) | C191023 | 1N5819WS | — | SOD-323 | 40 V 1 A, IR 500 µA@40 V. The only Basic SOD-323 Schottky; far leakier | Basic | 5,195,183 | — | not queried | [LCSC](https://www.lcsc.com/product-detail/C191023.html) / [JLC](https://jlcpcb.com/partdetail/C191023) |

Notes for B:
- **12**: no JLC Basic 220 nF **50 V** 0603 exists (a Basic-only search found only C21120 at 25 V 0603, C5378 at 50 V 0805 and C16772 at 16 V 0402).
- **14**: 75k and 18k 0402 have no Basic part. The UNI-ROYAL parts are *Preferred* Extended, so no loading fee. LCSC shows 0 stock for C25798 but JLC holds 57k.
- **15**: TI SN74LVC3G17 pinout (SCES470) is 1:1A, 2:3Y, 3:2A, 4:GND, 5:2Y, 6:3A, 7:1Y, 8:VCC, and is the same on DCT and DCU. JLC has no Basic 74LVC part.
- **16**: the TI part is specified at VCC ≤ 3.6 V, and its inputs are 5.5 V-tolerant.
- **17**: no Basic PTC fuses or load switches exist in the JLC library. TPS22946 (C130053) is DSBGA-6 only, with 190 in stock. It is not SC-70 and was rejected.
- **18**: no Basic BAT54 variant exists.

## C. KiCad footprints (/usr/share/kicad/footprints)

| Requested | Found (exact name) |
|---|---|
| Inductor_SMD:L_Changjiang_FNR5040S | `Inductor_SMD:L_Changjiang_FNR5040S` ✔ (no FHD4020S footprint; `L_Changjiang_FNR4020S` exists but that is a different series) |
| Diode_SMD:D_SMA | `Diode_SMD:D_SMA` ✔ (also `D_SMA_Handsoldering`) |
| Package_SO:VSSOP-8_2.3x2mm_P0.5mm (SN74LVC3G17DCU) | `Package_SO:VSSOP-8_2.3x2mm_P0.5mm` ✔; for DCT use `Package_SO:SSOP-8_2.95x2.8mm_P0.65mm` ✔ |
| Package_SO:TSSOP-14_4.4x5mm_P0.65mm | `Package_SO:TSSOP-14_4.4x5mm_P0.65mm` ✔ (BQA alt: `Package_DFN_QFN:DHVQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm`, but its EP must be checked against the TI BQA drawing, UNVERIFIED) |
| Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm | ✔ exact (also a `_ThermalVias` variant) |
| Package_SO:MSOP-10_3x3mm_P0.5mm | `Package_SO:MSOP-10_3x3mm_P0.5mm` ✔ (no plain VSSOP-10 name; only HVSSOP-10 with EP) |
| Package_DFN_QFN:QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm | ✔ exact (also `_ThermalVias`) |
| Fuse:Fuse_0805_2012Metric / Fuse_0603 | `Fuse:Fuse_0805_2012Metric` ✔, `Fuse:Fuse_0603_1608Metric` ✔ (+ `_Pad…_HandSolder` variants) |
| Diode_SMD:D_SOD-323 | `Diode_SMD:D_SOD-323` ✔ (also `D_SOD-323F`, `D_SOD-323_HandSoldering`) |
| SC-70-5 (TPS22945) | `Package_TO_SOT_SMD:SOT-353_SC-70-5` ✔ |
| JST SM06B | `Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal` ✔ |
| (extra) DRV8316CR RGF VQFN-40 7x5 | **none**: no `Texas_RGF…` or VQFN-40 7x5 footprint in the stock library; a custom one is needed |

## D. Datasheets downloaded to `hardware/motor_board/datasheets/`

All were checked to begin with `%PDF-`. Each came from the LCSC `pdfUrl` given in the product JSON (datasheet.lcsc.com).

| File | Part | Pages |
|---|---|---|
| SN74LVC3G17_TI.pdf | SN74LVC3G17 (SCES470F) | 25 |
| SN74LVC08A_TI.pdf | SN74LVC08A (SCAS283T) | 36 |
| TPS22945_TI.pdf | TPS22941–TPS22945 | 24 |
| PTC_0603L_Littelfuse.pdf | Littelfuse 0603L series | 5 |
| SS34_MDD.pdf | MDD SS32–SS3200 | 3 |
| FNR5040S_CJiang.pdf | Changjiang FNR series (image-only PDF; FNR5040S table on p.13) | 19 |
| EEHZK_Panasonic_C278516.pdf | Panasonic ZK series (25–35 V) | 3 |
| XUNPU_WAFER-SH1.0-6PWB.pdf | XUNPU SH1.0 right-angle drawing | 1 |
| LXWCONN_SH1.0mm-6P-WT.pdf | LXWCONN SH1.0 right-angle drawing | 1 |
| BAT54WS_Diodes.pdf | Diodes BAT54WS (extra) | 5 |

## Items to watch
- **Low stock**: DRV8323RHRGZR (203) and INA239AIDGSR (111). Reserve or preorder these before ordering the board.
- EEHZK1V331P ripple: the LCSC field reads "420 mA@100Hz", but the Panasonic ZK table gives **2800 mA rms at 100 kHz/125 °C** and ESR 20 mΩ for case G (10 x 10.2). Use the datasheet figures.
- FNR5040S220MT: 1.6 A is the guaranteed Isat and 1.8 A is typical. The heat-rating current is 1.5 A.
- SH clones: tab positions and the pin-1 end are UNVERIFIED against a physical sample (see A11).
