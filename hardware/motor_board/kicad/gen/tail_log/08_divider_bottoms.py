"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
    # divider bottoms R23 (W_VA) and R25 (W_VB) sat ~15 mm west of the rest of their nets: beside their tops R22 / R24
    dict(op="rip_ref", ref="R23"), dict(op="rip_ref", ref="R25"),
    dict(op="move", ref="R23", x=60.8, y=4.45, rot=90, side="B"),
    dict(op="move", ref="R25", x=48.81, y=5.45, rot=0, side="B"),
    dict(op="route", net="W_VA", a=("pad", "R23", "1"), b=("pad", "R22", "2"), w=0.15, margin=1.5, layers=["B.Cu"]),
    dict(op="route", net="W_VB", a=("pad", "R25", "1"), b=("pad", "R24", "2"), w=0.15, margin=1.5, layers=["B.Cu"]),
    dict(op="drop", pad=("R23", "2"), net="GND", margin=2.0, w=0.25, via=0.4, drill=0.2),
    dict(op="drop", pad=("R25", "2"), net="GND", margin=2.0, w=0.25, via=0.4, drill=0.2),
]
