# Schematic sheets: parts and cross-sheet labels

Generated from design/netlist.csv (the reviewed netlist).  Every part lives on exactly one sheet;
nets that join parts on different sheets need a **global label** of that exact name on each of
those sheets.  GND, +3V3 and +5V use KiCad power symbols instead.  Nets not listed below stay
inside one sheet: draw them as plain wires (or local labels).

## power

**Parts:** C1, C2, C3, C4, C5, C6, C7, C8, C9, C11, C12, C13, C14, C18, C19, D1, D4, D5, D10, J4, JBAT1, JBAT2, Q7, Q8, R1, R2, R3, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R32, R42, RS4, TP9, U7, U8, U13

**Global labels:** BMS_ALERT, BMS_SCL, BMS_SDA, INA_nCS, SPI_MISO, SPI_MOSI, SPI_SCK, VBAT, W_nFAULT

## weapon

**Parts:** C10, C15, C16, C17, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30, C31, C40, D2, D9, JW1, JW2, JW3, L1, NT1, NT2, NT3, Q1, Q2, Q3, Q4, Q5, Q6, R4, R5, R18, R19, R20, R21, R22, R24, R26, R41, R44, R45, R46, R47, R48, R49, RS1, RS2, RS3, TH1, TP6, TP10, U2, U6, U14

**Global labels:** VBAT, W_ARM_CLK, W_ARM_S, W_EN, W_INHA, W_INHB, W_INHC, W_INLA_M, W_INLB_M, W_INLC_M, W_NTC, W_SOA, W_SOB, W_SOC, W_VA, W_VB, W_VC, W_nFAULT

## drive_left

**Parts:** C300, C301, C302, C303, C304, C305, C306, C307, C308, C309, C310, JL1, JL2, JL3, R300, R301, R302, U3

**Global labels:** DRV_OFF, L_INHA, L_INHB, L_INHC, L_SOA, L_SOB, L_SOC, L_nCS, L_nFAULT, SPI_MISO, SPI_MOSI, SPI_SCK, VBAT

## drive_right

**Parts:** C400, C401, C402, C403, C404, C405, C406, C407, C408, C409, C410, JR1, JR2, JR3, R50, R400, R401, R402, TP8, U4

**Global labels:** DRV_OFF, R_INHA, R_INHB, R_INHC, R_SOA, R_SOB, R_SOC, R_nCS, R_nFAULT, SPI_MISO, SPI_MOSI, SPI_SCK, VBAT

## mcu

**Parts:** C41, C42, C43, C44, C60, C61, C62, C63, C64, C65, C66, C67, C68, C69, C70, C71, C74, C80, C81, C82, C90, C91, C92, D3, J1, R16, R17, R23, R25, R27, R33, R40, R43, R60, R61, R62, R63, R64, R70, R71, R72, R80, R81, R82, TP1, TP2, TP3, TP4, TP5, TP7, TP11, TP12, U1, U5

**Global labels:** BMS_ALERT, BMS_SCL, BMS_SDA, DRV_OFF, INA_nCS, L_INHA, L_INHB, L_INHC, L_MTEMP, L_S1, L_S2, L_S3, L_SOA, L_SOB, L_SOC, L_nCS, L_nFAULT, R_INHA, R_INHB, R_INHC, R_MTEMP, R_S1, R_S2, R_S3, R_SOA, R_SOB, R_SOC, R_nCS, R_nFAULT, SPI_MISO, SPI_MOSI, SPI_SCK, VBAT, W_ARM_CLK, W_ARM_S, W_EN, W_INHA, W_INHB, W_INHC, W_INLA_M, W_INLB_M, W_INLC_M, W_NTC, W_SOA, W_SOB, W_SOC, W_VA, W_VB, W_VC, W_nFAULT

## sensors

**Parts:** C45, C46, C47, C48, C49, C50, C72, C73, C110, C111, C112, C114, C115, C116, D7, D8, J2, J3, JP1, JP2, R52, R53, R54, R55, R56, R57, R58, R59, R110, R111, R112, R113, R114, R115, R116, R117, U9, U10, U11, U12

**Global labels:** L_MTEMP, L_S1, L_S2, L_S3, R_MTEMP, R_S1, R_S2, R_S3
