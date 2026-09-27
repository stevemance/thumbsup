"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
]
EDITS += [dict(e, margin=7.0, max_ratio=2.0, w=(0.2 if e["net"] in ("+3V3", "+5V") else 0.127), **({"avoid": [["F.Cu", 42.6, 21.5, 45.7, 27.6]]} if e["net"] == "+5V" else {})) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "13_input_drc.json", skip=("GND", "/drive_right/R_VM"))]
