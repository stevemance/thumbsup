"""v2 closing pre-route (P5): the signal / rail opens the earlier stages left, on top of v2_rear.  Experiment module
for tail.py:

    cd kicad/gen && TAIL_EXP=v2_close TAIL_BASE=<abs>/kicad/gen/out/exp/v2_rear/proj/motor_board.kicad_pcb /usr/bin/python3 tail.py

The connections are taken from the base board's DRC report (out/exp/v2_rear/drc.json, a minimum spanning set per net).
Rules: v2_pre.py.  What this stage closes and why the rest stays open: kicad/v2/out/prerout_progress.txt (P5 lines).

Findings that bound this stage (2026-09-30, grid router + Freerouting probes, kicad/v2/out/fr_close, fr_strip):
  - most remaining pads are boxed in with no legal via site (U7 rear pin pocket, U9 under J2.MP, MCU rear-row pins
    49/50/59/60, the J1 row gap held by R_H2 / NRST on L4, U8's east/west sides, the BMS R-row under the W_IN* L3
    lanes); Freerouting with the earlier copper locked closes 10 of 48 items, after stripping the router-made copper
    of ilock/sense/rear it leaves 32 items open and breaks 300 layer rules (analog shadow / analog on L4 / stacked);
  - so only the local connections that route within the rules (analog: crossings logged, no stacked runs) are made
    here; the long MCU <-> J1 / BMS / TH1 / U7 nets need the structural changes listed in the progress log."""
import json
import os
import re
from pathlib import Path

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, chain, tr, via, PV, POFV, RV, n_  # noqa: F401

HERE = Path(__file__).resolve().parent
BASE_EXP = "v2_rear"
v2_pre.STACK_PEN = 8.0
LAYER = {"L1.TOP": F1, "L4.BOT": L4, "L3.PWR_GND": L3}
SEC = os.environ.get("SEC", "all").split(",")


def on(s):
    return "all" in SEC or s in SEC


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
    d = json.load(open(HERE / "out" / "exp" / BASE_EXP / "drc.json"))
    out = []
    for u in d["unconnected_items"]:
        m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
        if m and m.group(1).split("/")[-1] in nets:
            out.append((m.group(1).split("/")[-1], end(u["items"][0]), end(u["items"][1])))
    return out


def why(net, a, b, **kw):
    route(net, a, b, **kw)
    EDITS[-1]["op"] = "why"


SIGNALS = ["W_nFAULT", "W_INLB_M", "BMS_ALERT", "BMS_BAT", "L_H2", "L_H2B", "L_H3B", "L_S3", "L_MTEMP", "W_NTC",
           "SWDIO", "SWCLK", "MB_TX", "MB_RX", "VBAT_SNS", "CELL0", "CELL1", "CELL2", "CELL3", "CELL4"]
RAILS = ["+5V", "+3V3"]
THIN = dict(w=0.15, via=0.4, drill=0.2)            # rail neck-down (as region 3)

if on("probe"):          # one request per open (diagnostics: /tmp reach.py)
    for net in os.environ.get("PNETS", "").split(","):
        for n, a, b in opens([net]):
            route(n, a, b, margin=float(os.environ.get("PM", "4")), tag=f"{n_(n)} {a[1]}-{b[1]}",
                  no_shadow=bool(os.environ.get("NOSH")), **(THIN if os.environ.get("THIN") else {}))

if on("close"):
    # +5V: JP2.3 to J1.2 (the J1 +5V pins; J1.1 / R62 island stays open: J1's column x 81.0 is covered by J3's pads
    # on L1 and crossed by NRST / SWCLK on L4)
    for n, a, b in opens(["+5V"]):
        if a[0] == "pad" and b[0] == "pad" and {a[1], b[1]} == {"J1", "JP2"}:
            route(n, a, b, margin=4.0, tag=f"+5V {a[1]}-{b[1]}", **THIN)
    # J1.1 (+5V, with R62) to J1.2: NRST's L4 run along J1's row gap (J1.8 -> C67 / R16) moves to L3 so the +5V
    # column x 81.0 can cross the gap on L4
    EDITS.append(dict(op="rip", box=(77.6, 21.5, 82.55, 22.7), nets=[n_("NRST")], layers=[L4]))
    route("NRST", P("J1", 8), ("pt", 82.6, 21.45, L4), margin=3.0, tag="NRST J1.8-C67 (L3 hop)",
          avoid=[[L4, 77.55, 22.27, 82.45, 23.73, "tracks"]])
    # R_H2 (J3.4 -> R58.1) leaves the row gap too: L3 from its J3 via to R58
    EDITS.append(dict(op="rip", box=(75.25, 23.3, 82.9, 26.45), nets=[n_("R_H2")], layers=[L4]))
    via("R_H2", (76.05, 29.24))
    tr("R_H2", L4, [(76.05, 29.24), (75.55, 29.24)])
    route("R_H2", ("via", 82.95, 23.65), ("via", 76.05, 29.24), [L3], margin=4.0, tag="R_H2 J3-R115 (L3)")
    route("+5V", P("J1", 1), P("J1", 2), margin=1.5, tag="+5V J1.1-J1.2", **THIN)
    # L_MTEMP: U1.6 -> C72.1 (L1 over to the bottom cap; crossing logged by rules.py)
    for n, a, b in opens(["L_MTEMP"]):
        if "C72" in (a[1], b[1]):
            route(n, a, b, margin=4.0, tag=f"L_MTEMP {a[1]}-{b[1]}", no_shadow=True)
    # BMS: only U8's own CELL2 pin pair (pins 1/2).  The cap legs at the R-row (C4-C7) route only as L4 runs stacked
    # under the W_INHx L3 lanes (1.5-1.8 mm, CELL3 / CELL2) and would be ripped again when C4-C8 move to U8: left open
    for n, a, b in opens(["CELL2"]):
        if a[1] == "U8" and b[1] == "U8":
            route(n, a, b, margin=2.0, tag="CELL2 U8.1-U8.2", stub=True, no_shadow=True)
