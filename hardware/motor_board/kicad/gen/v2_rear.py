"""v2 region 3 pre-route (P3/P5): the rear-right header J1 (bottom), SWD (SWDIO / SWCLK / NRST), MB_TX / MB_RX,
VBAT_SNS_H, the BMS (U8 + J4: I2C / ALERT, CELLx / BALx, BMS_BAT / BMS_REG), INA_nCS, the +3V3 / +3V3A / +5V trunks
and the small front-band leftovers (PSW_*, INA_INN / INA_INP), on top of v2_sense.  Experiment module for tail.py:

    cd kicad/gen && TAIL_EXP=v2_rear TAIL_BASE=<abs>/kicad/gen/out/exp/v2_sense/proj/motor_board.kicad_pcb /usr/bin/python3 tail.py

The connections are taken from the base board's own DRC report (out/exp/v2_sense/drc.json: its unconnected pairs are
a minimum spanning set per net), so every open of the region's nets becomes one router request; explicit copper first
where the router needs a path planned (INA_nCS out of U7's rear pin pocket through the C407 pad gap).  Rules:
v2_pre.py."""
import json
import re
from pathlib import Path

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV, n_  # noqa: F401

HERE = Path(__file__).resolve().parent
v2_pre.STACK_PEN = 8.0
LAYER = {"L1.TOP": F1, "L4.BOT": L4, "L3.PWR_GND": L3}


def end(item):
    d, pos = item["description"], item["pos"]
    x, y = round(pos["x"] - 100.0, 4), round(pos["y"] - 70.0, 4)
    m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[.*?\] of (\S+)", d)
    if m:
        return ("pad", m.group(2), m.group(1))
    if d.startswith("Via"):
        return ("via", x, y)
    m = re.search(r" on (\S+)", d)
    return ("pt", x, y, LAYER[m.group(1).rstrip(",")])


def opens(nets):
    d = json.load(open(HERE / "out" / "exp" / "v2_sense" / "drc.json"))
    out = []
    for u in d["unconnected_items"]:
        m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
        if m and m.group(1).split("/")[-1] in nets:
            out.append((m.group(1).split("/")[-1], end(u["items"][0]), end(u["items"][1])))
    return out


def route_opens(nets, **kw):
    for net in nets:
        for n, a, b in opens([net]):
            route(n, a, b, **kw)


# ---------------------------------------------------------------- INA_nCS: U7.1 out of its rear-pin pocket
# (C407 below, R_FBBK and the SPI_MISO via beside it): L1 down the C407 pad gap to a via under it, L3 east along
# y 20.25 (north of the R_INHC lane) to a via at C61's west side, L4 into R12.1; L1 along the MCU's front (y 19.45,
# in front of pins 32-24) into pin 23's outer end.
tr("INA_nCS", F1, [(26.5, 17.9), (26.5, 18.4), (27.35, 19.25), (27.35, 20.25)])
via("INA_nCS", (27.35, 20.25))
tr("INA_nCS", L3, [(27.35, 20.25), (33.35, 20.25), (33.4, 20.3)])
via("INA_nCS", (33.4, 20.3))
tr("INA_nCS", L4, [(33.4, 20.3), (33.6, 20.5), (33.75, 21.45)])
tr("INA_nCS", F1, [(33.4, 20.3), (33.4, 19.75), (33.7, 19.45), (38.45, 19.45), (38.75, 19.75), (38.75, 20.0)])

# ---------------------------------------------------------------- BMS / J1 hops
# BMS_SCL (U8.12) to J1.16 in J1's far row: east of U8, through the J1.15 | J1.17 pad gap; BMS_SDA east of it into
# J1.15; BMS_BAT straight from R11.2 up into U8.16; VBAT_SNS_H from R33.2 north west of R58 into J1.11
tr("BMS_SCL", L4, [(71.6, 28.5), (71.95, 28.5), (71.95, 26.9), (71.49, 26.44), (71.49, 22.6), (71.9, 22.2)])
tr("BMS_SDA", L4, [(71.6, 29.0), (72.3, 29.0), (72.3, 26.1)])
tr("BMS_BAT", L4, [(70.6, 30.9), (70.6, 32.2)])
tr("VBAT_SNS_H", L4, [(74.2, 29.1), (73.95, 28.85), (73.95, 26.6), (74.4, 26.15), (74.6, 25.9)])

# ---------------------------------------------------------------- locals first, then the long runs, rails last
LOCAL = ["LED_A", "BMS_REG", "BMS_SDA", "BMS_SCL", "BMS_ALERT", "VBAT_SNS_H", "PSW_RG", "PSW_CAP", "PSW_DV", "PSW_EN",
         "PSW_G", "INA_INN", "INA_INP", "BMS_BAT", "BAL0", "BAL1", "BAL2", "BAL3", "BAL4"]
LONG = ["CELL0", "CELL1", "CELL2", "CELL3", "CELL4", "NRST", "MB_TX", "MB_RX", "SWDIO", "SWCLK", "VBAT_SNS",
        "L_MTEMP", "W_nFAULT"]
RAILS = ["+3V3A", "+5V", "+3V3"]
# BAL: J4 pin -> series resistor hops (2 mm, L4 across the digital L3 lanes between J4 and the R-row: a local
# bottom-pad hop, the shadow rule waived for it and listed)
route_opens([n for n in LOCAL if n.startswith("BAL")], margin=1.5, no_shadow=True, stub=True)
route_opens([n for n in LOCAL if not n.startswith("BAL")], margin=2.5)
route_opens(LONG, margin=5.0)
route_opens(RAILS, margin=3.0)
# second pass for the rail hops that failed: 0.15 mm neck-down, 0.4 / 0.2 vias, wider search window
for net in RAILS:
    for n, a_, b_ in opens([net]):
        route(n, a_, b_, margin=6.0, w=0.15, via=0.4, drill=0.2, retry=True,
              tag=f"{n_(n)} {a_[1]}-{b_[1]}")
for net in LONG:
    for n, a_, b_ in opens([net]):
        route(n, a_, b_, margin=8.0, retry=True, tag=f"{n_(n)} {a_[1]}-{b_[1]}")

# ---------------------------------------------------------------- GND pads the stitching (v2/gndvias.py) finds no spot for
# (its list on this region's output; the exposed pads and the DRV8316 / DRV8323 GND pins tied to them get their thermal
# via arrays with the pours): a drop to the nearest legal via spot, routed round the new copper
NO_SPOT = """D5.2 U7.7 C305.2 U1.15 U1.27 U1.31 R40.2 C406.2 C22.2 D2.2 J3.2 C300.2 C10.2 C306.2 R21.2 R5.2 C301.2 C23.2
U13.2 U5.2 C407.2 R46.2 C405.2 J2.2 J2.MP U9.4 J1.3 J1.4 C49.2 R64.2 C17.2 C65.2 C40.2 C47.2 R19.2 R25.2 C82.2 C110.2
U8.6 U8.7 U8.8 U8.11 D8.1 C70.2 C81.2 C73.2 C80.2 U10.4 U14.3 C41.2 C19.2 R47.2 C11.2 C111.2 U11.2 C69.2 C60.2 C114.2
C45.2 C72.2 C43.2 D9.1 C16.2 R23.2 C71.2 C8.2 R41.2 D3.1 C50.2 C63.2 C91.2 R18.2 C66.2 R27.2 U6.7 U2.34 U2.35""".split()
for rp in NO_SPOT:
    ref, num = rp.split(".")
    EDITS.append(dict(op="drop", pad=(ref, num), net="GND", margin=2.5, w=0.25, via=0.45, drill=0.25))
