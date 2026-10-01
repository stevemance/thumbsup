"""h4: router flow on top of a hand stage (H4_BASE, default h3): r2_main's groups and rip-up/reroute passes, without
r2_main's explicit U2 rear fan-out (the hand stage owns it).  H4_ORDER overrides the group order."""
import os

import v2_pre
from v2_pre import EDITS  # noqa: F401
import r2_auto as A

v2_pre.VIA_PITCH = 0.9
v2_pre.STACK_PEN = 8.0
BASE = os.environ.get("H4_BASE", "h3")

RAILS = ["+3V3", "+5V", "+3V3A"]
ANALOG = ["R_MTEMP", "L_MTEMP", "L_TEMPJ", "W_NTC", "W_SOA", "W_SOB", "W_SOC", "W_VA", "W_VB", "W_VC", "VBAT_SNS",
          "VBAT_SNS_H"]
LONG = ["W_INLA", "W_INLB", "W_INLC", "W_INHA", "W_INHB", "W_INHC", "W_INLA_M", "W_INLB_M", "W_INLC_M", "W_nFAULT",
        "INA_nCS", "BMS_SDA", "BMS_SCL", "BMS_ALERT", "BMS_BAT", "R_S1", "R_S2", "R_S3", "L_S1", "L_S2", "L_S3",
        "NRST", "SWDIO", "SWCLK", "MB_TX", "MB_RX", "W_EN", "W_ARM_S", "W_ARM", "W_ARM_CLK", "ARM_AC", "CELL0", "CELL1",
        "LED_A"]
LOCAL = ["U2_DVDD", "U2_IDRIVE", "U2_MODE", "U2_VDS", "INA_INN", "INA_INP", "PSW_CAP", "PSW_DV", "PSW_EN", "PSW_G",
         "PSW_RG", "R_H2B", "L_H1", "L_H2", "L_H3", "L_H1B", "L_H2B", "L_H3B", "L_VS", "L_VSRC", "L_AVDD", "L_nFAULT"]
G = {"rails": RAILS, "analog": ANALOG, "long": LONG, "local": LOCAL}
ORDER = os.environ.get("H4_ORDER", "rails,analog,long,local").split(",")
for g in ORDER:
    A.route_opens(BASE, G[g], margin=4.0, soft=(g != "rails"))
for g in ORDER:
    A.route_opens(BASE, G[g], margin=9.0, retry=True, soft=(g != "rails"))
