"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# C50 (U10 VCC decap) 2.3 mm north: GND via, +3V3 straight to U10.8
EDITS = [
    dict(op="rip_ref", ref="C50"),
    dict(op="move", ref="C50", x=70.5, y=22.3, rot=180.0, side="B"),
    dict(op="drop", pad=("C50", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
    dict(op="route", net="+3V3", a=("pad", "C50", "1"), b=("pad", "U10", "8"), layers=["B.Cu", "In4.Cu", "F.Cu", "In2.Cu"], layer_cost={"In4.Cu": 1.5}, w=0.2, margin=3.0, max_ratio=5.0),
]
