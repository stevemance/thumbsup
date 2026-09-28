"""Router requests for the open connections in a DRC report (frozen/drc.json by default):
    from tail_auto import auto; EDITS += auto(skip=("GND",), only=None)
A pad end is ("pad", ref, num); a track end is ("pt", x, y, layer); a via end is ("via", x, y).  Zone-to-zone items
(pour islands) are skipped.  DRC positions are absolute; board-local = absolute - (100, 70) on this board."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LN = {"F.Cu": "F.Cu", "B.Cu": "B.Cu", "L3.PWR+SIG": "In2.Cu", "L4.SIG": "In3.Cu", "L5.GND": "In4.Cu"}


def end(i, bx, by):
    d = i["description"]
    x, y = round(i["pos"]["x"] - bx, 4), round(i["pos"]["y"] - by, 4)
    m = re.match(r"Pad (\S+) \[[^\]]*\] of (\S+)", d)
    if m:
        return ("pad", m.group(2), m.group(1))
    if d.startswith("Via"):
        return ("via", x, y)
    if d.startswith("Track"):
        return ("pt", x, y, LN[re.search(r" on ([^ ,]+)", d).group(1)])
    return None


def auto(drc=HERE / "frozen" / "drc.json", skip=("GND",), only=None, margin=6.0, w=0.15, bx=100.0, by=70.0):
    out = []
    for u in json.load(open(drc))["unconnected_items"]:
        net = re.search(r"\[([^\]]+)\]", u["items"][0]["description"]).group(1)
        if net in skip or (only and net not in only):
            continue
        a, b = (end(i, bx, by) for i in u["items"])
        if a is None or b is None:
            continue
        out.append(dict(op="route", net=net, a=a, b=b, w=w, margin=margin))
    return out
