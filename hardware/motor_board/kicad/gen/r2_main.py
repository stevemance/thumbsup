"""r2 stage: everything that is not pre-routed yet, on top of r2_senr (router, rip-up-and-reroute on), with the U2 rear
gate-input fan-out drawn explicitly: INL pins 38/40/42 drop to vias right behind the pins (staggered, >= 1.35 mm
apart) and run to U6 on the bottom; INH pins 37/39/41 pass between those vias and turn west as a 3-track bus at
y 29.5 / 29.85 / 30.2 under J4's front edge.  Order: rails, long analog, long digital, locals (R2_ORDER overrides).
Rules: v2_pre (band, islands, fields, analog shadow), via pitch 0.9, L3 discouraged for digital / rail nets."""
import os

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV  # noqa: F401
import r2_auto as A

v2_pre.VIA_PITCH = 0.9
v2_pre.STACK_PEN = 8.0
BASE = os.environ.get("R2_BASE", "r2_senr")

# ---------------------------------------------------------------- U2 rear gate inputs
for n, x, vy in (("W_INLA", 61.25, 28.4), ("W_INLB", 62.25, 29.3), ("W_INLC", 63.25, 28.4)):
    tr(n, F1, [(x, 27.7), (x, vy)])
    via(n, (x, vy))
for n, x, y in (("W_INHA", 60.75, 29.5), ("W_INHB", 61.75, 29.85), ("W_INHC", 62.75, 30.2)):
    tr(n, F1, [(x, 27.7), (x, y), (60.0, y)])

RAILS = ["+3V3", "+5V", "+3V3A"]
ANALOG = ["R_MTEMP", "L_MTEMP", "W_NTC", "W_SOA", "W_SOB", "W_SOC", "W_VA", "W_VB", "W_VC", "VBAT_SNS", "VBAT_SNS_H"]
LONG = ["W_INLA", "W_INLB", "W_INLC", "W_INHA", "W_INHB", "W_INHC", "W_INLA_M", "W_INLB_M", "W_INLC_M", "W_nFAULT",
        "INA_nCS", "BMS_SDA", "BMS_SCL", "BMS_ALERT", "BMS_BAT", "R_S1", "R_S2", "R_S3", "L_S1", "L_S2", "L_S3",
        "NRST", "SWDIO", "SWCLK", "MB_TX", "MB_RX", "W_EN", "W_ARM_S", "W_ARM", "W_ARM_CLK", "ARM_AC", "CELL0", "CELL1"]
LOCAL = ["U2_DVDD", "U2_IDRIVE", "U2_MODE", "U2_VDS", "INA_INN", "INA_INP", "PSW_CAP", "PSW_DV", "PSW_EN", "PSW_G",
         "PSW_RG", "LED_A", "R_H2B", "L_H1", "L_H2", "L_H3", "L_H1B", "L_H2B", "L_H3B", "L_VS", "L_VSRC", "L_TEMPJ",
         "L_AVDD", "L_nFAULT"]
ORDER = os.environ.get("R2_ORDER", "rails,analog,long,local").split(",")
G = {"rails": RAILS, "analog": ANALOG, "long": LONG, "local": LOCAL}
for g in ORDER:
    A.route_opens(BASE, G[g], margin=4.0, soft=(g != "rails"))
for g in ORDER:
    A.route_opens(BASE, G[g], margin=9.0, retry=True, soft=(g != "rails"))
