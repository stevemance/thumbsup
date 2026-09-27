"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L4 = "In3.Cu"

EDITS = [
]
from tail_auto import auto  # noqa: E402
EDITS += auto(skip=("GND", "+3V3", "+5V", "/drive_right/R_VM", "/drive_left/L_VM", "/power/BAT_IN", "/power/VBAT_SW"))
# +3V3 on L4: the spare area of L4 poured with +3V3 (lowest priority, around every signal), each stranded +3V3 pad
# dropped to it
EDITS = [e for e in EDITS if e["op"] != "route"]
EDITS.append(dict(op="zone", net="+3V3", layer=L4, name="L4 3V3 fill", clr=0.15, min_w=0.2))
import json as _j, re as _re  # noqa: E402
_seen = set()
for _u in _j.load(open(__import__("pathlib").Path(__file__).resolve().parent / "frozen" / "drc.json"))["unconnected_items"]:
    for _i in _u["items"]:
        _m = _re.match(r"Pad (\S+) \[\+3V3\] of (\S+)", _i["description"])
        if _m and (_m.group(2), _m.group(1)) not in _seen:
            _seen.add((_m.group(2), _m.group(1)))
            EDITS.append(dict(op="drop", pad=(_m.group(2), _m.group(1)), net="+3V3", margin=3.5, w=0.2, via=0.4, drill=0.2))
