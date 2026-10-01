#!/bin/bash
# r2/auto.sh <base exp>   : r2_auto (every open, group order below) on the base stage
export R2_BASE="$1"
export R2_NETS="${R2_NETS:-U2_DVDD,U2_IDRIVE,U2_MODE,U2_VDS,INA_INN,INA_INP,PSW_CAP,PSW_DV,PSW_EN,PSW_G,PSW_RG,LED_A;BAL0,BAL1,BAL2,BAL3,BAL4,CELL0,CELL1,CELL2,CELL3,CELL4,BMS_REG,BMS_BAT;R_H1,R_H2,R_H3,R_H1B,R_H2B,R_H3B,R_VS,R_VSRC,R_TEMPJ;L_H1,L_H2,L_H3,L_H1B,L_H2B,L_H3B,L_VS,L_VSRC,L_TEMPJ,L_AVDD,L_nFAULT;W_VA,W_VB,W_VC,VBAT_SNS,VBAT_SNS_H,W_ARM,W_ARM_CLK,ARM_AC,W_ARM_S,W_EN,W_nFAULT,W_INLA_M,W_INLB_M,W_INLC_M,W_INLA,W_INLB,W_INLC,W_INHA,W_INHB,W_INHC,W_SOA,W_SOB,W_SOC,INA_nCS;NRST,SWDIO,SWCLK,MB_TX,MB_RX,BMS_SDA,BMS_SCL,BMS_ALERT,R_S1,R_S2,R_S3,L_S1,L_S2,L_S3,L_MTEMP,R_MTEMP,W_NTC;+3V3A,+5V,+3V3}"
D="$(dirname "$0")"
"$D/stage.sh" r2_auto "$1" | grep -E "DRC|FAIL|router"
cd "$D/.." && python3 r2/opens.py r2_auto && python3 r2/rules.py "$1" r2_auto | grep -E "new L3|analog on|PITCH|stacked" | head -8
