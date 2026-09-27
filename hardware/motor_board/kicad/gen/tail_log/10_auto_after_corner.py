"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
]
EDITS += [dict(e, margin=8.0, **({"avoid": [["F.Cu", 42.6, 21.5, 45.7, 27.6]]} if e["net"] == "+5V" else {})) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "10_input_drc.json", skip=("GND",))]
