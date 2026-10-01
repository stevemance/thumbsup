"""r2 helper: route a base stage's opens with the grid router, net group by net group (v2_pre rules: band / islands /
fields, analog shadow; r2: via pitch 0.9, L3 discouraged for digital nets so the L3 GND pour stays whole).
Imported by the r2 region stages; standalone for experiments:
    R2_BASE=<exp> R2_NETS="a,b;c,d" TAIL_EXP=r2_auto ..."""
import json
import os
import re
from pathlib import Path

import v2_pre
from v2_pre import EDITS, F1, L3, L4, route, n_  # noqa: F401

v2_pre.VIA_PITCH = 0.9
HERE = Path(__file__).resolve().parent
LAYER = {"L1.TOP": F1, "L4.BOT": L4, "L3.PWR_GND": L3}
STUB_NETS = {"CELL0", "CELL1", "CELL2", "CELL3", "CELL4", "BAL0", "BAL1", "BAL2", "BAL3", "BAL4"}


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


def opens(base, nets):
    d = json.load(open(HERE / "out" / "exp" / base / "drc.json"))
    out = []
    for u in d["unconnected_items"]:
        m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
        if m and m.group(1).split("/")[-1] in nets:
            out.append((m.group(1).split("/")[-1], end(u["items"][0]), end(u["items"][1])))
    return out


def route_opens(base, nets, skip=(), **kw):
    for net in nets:
        for n, a, b in opens(base, [net]):
            if (n, a[1], b[1]) in skip or (n, b[1], a[1]) in skip:
                continue
            k = dict(kw)
            if n in STUB_NETS:
                k.setdefault("stub", True)
            if not v2_pre.is_analog(n):
                k.setdefault("layer_cost", {L3: float(os.environ.get("R2_L3COST", "6"))})
            k.setdefault("soft", True)
            route(n, a, b, tag=f"{n} {a[1]}-{b[1]}", **k)


if os.environ.get("R2_BASE") and __name__ != "__main__" and os.environ.get("TAIL_EXP") == "r2_auto":
    v2_pre.STACK_PEN = 8.0
    for grp in os.environ["R2_NETS"].split(";"):
        route_opens(os.environ["R2_BASE"], grp.split(","), margin=float(os.environ.get("R2_M", "4")))
