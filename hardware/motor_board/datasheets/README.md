# Motor board datasheets (downloaded 2026-09-23/24)

| File | Part (refs) | Source |
|---|---|---|
| STM32G474RET6.pdf | MCU (U1) | LCSC mirror of ST DS12288 (st.com blocks scripted downloads) |
| DRV8323.pdf | weapon gate driver + buck, DRV8323RH (U2) | ti.com SLVSDJ3D (covers the H and S variants) |
| DRV8316C.pdf | drive motor drivers, DRV8316CR (U3, U4) — **the fitted part** | ti.com SLVSH07 |
| DRV8316.pdf | DRV8316R/T (the rev A part), kept for reference only | ti.com SLVSF16B |
| LMR16006.pdf | the buck core inside U2 (L1, D2, R20/R21, R4/R5 UVLO) | ti.com SNVSA24 |
| LM74502.pdf | power-switch controller (U13), Q7/Q8 gate drive, soft-start, UVLO | ti.com SNOSDE5A |
| INA239.pdf | pack monitor (U7) — fitted | ti.com |
| INA229.pdf | pin/footprint-compatible alternative for U7 (different register widths) | ti.com |
| BQ76907.pdf | cell monitor (U8) | ti.com |
| AP2112K.pdf | 3.3 V LDO (U5) | Diodes Inc. |
| SN74LVC08A_TI.pdf | weapon interlock quad AND (U6) | ti.com SCAS283 |
| SN74LVC3G17_TI.pdf | sensor Schmitt buffers (U9, U10) | ti.com SCES470 |
| 74LVC1G17_Diodes.pdf | ARM Schmitt buffer (U14; SOT-353 pin 1 NC, 2 A, 3 GND, 4 Y, 5 VCC) | Diodes DS35124 |
| TPS22945_TI.pdf | sensor supply current-limited switches (U11, U12) | ti.com SLVS832D |
| HYG015N04LS1C2.pdf | weapon FETs Q1–Q6, power-switch FETs Q7/Q8 | LCSC mirror of HUAYI |
| HoLR2512-3W-2mR.pdf | weapon shunts RS1–RS3 (1–4 mΩ land pattern) | LCSC mirror of Milliohm |
| RE2512F3R001_1mR.pdf | pack shunt RS4 | LCSC mirror of JIERR |
| SMBJ20A_BORN.pdf | TVS D1 | LCSC mirror of BORN |
| EEHZK_Panasonic_C278516.pdf | bulk capacitor C1 (EEHZK1V331P) | LCSC mirror of Panasonic |
| FNR5040S_CJiang.pdf | buck inductor L1 (FNR5040S table on p.13; scanned) | LCSC mirror |
| SS34_MDD.pdf | buck catch diode D2 | LCSC mirror of MDD |
| MMSZ5242B.pdf | Q7/Q8 gate-source zener D4 | LCSC mirror |
| B5819W_CJ.pdf | VC0 clamp D5 | LCSC mirror of CJ |
| UNIROYAL_2512_thick_film.pdf | DRV8316 VM feed resistors R302/R402 (25121WF100LT4E) | LCSC mirror of UNI-ROYAL |
| 1N4148W.pdf | Cdvdt steering diode D10 | LCSC mirror |
| BAV99_Nexperia.pdf | motor-NTC clamps D7, D8 (1 A1, 2 K2, 3 K1/A2) | LCSC mirror of Nexperia |
| BAT54S_Nexperia.pdf | dynamic-ARM charge pump D9 (1 A1, 2 K2, 3 K1/A2) | LCSC mirror of Nexperia |
| NCP18XH103F03RB.pdf | FET NTC TH1 | LCSC mirror of Murata |
| LED_KT-0603R.pdf | power LED D3 | LCSC mirror of KENTO |
| XUNPU_WAFER-SH1.0-6PWB.pdf | sensor connectors J2, J3 (fitted; the custom footprint is drawn from this) | LCSC mirror |
| LXWCONN_SH1.0mm-6P-WT.pdf | alternate for J2, J3 | LCSC mirror |
| SM06B_JST_SH.pdf | JST original (mating SHR-06V-S housing, pin numbering reference) | jst-mfg.com |
| JST_XH.pdf | balance connector J4 | jst-mfg.com |
| BOOMELE_1.27-2x10P.pdf | header to the compute board J1 | LCSC mirror of BOOMELE |
| MT6701CT-STD.pdf | magnetic encoder for the drive-motor sensor boards (off-board) | LCSC mirror of MagnTek |

JLC Basic resistors/capacitors are generic parts and are not included.
