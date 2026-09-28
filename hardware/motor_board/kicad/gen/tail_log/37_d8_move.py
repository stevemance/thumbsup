"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# D8 (BAV99 clamp on R_MTEMP) from the far NW into the band beside R53 / C73 (same node, 17 mm closer)
ALL = ["F.Cu", "B.Cu", "In2.Cu", "In4.Cu"]
EDITS = [
    dict(op="rip_ref", ref="D8"),
    dict(op="move", ref="D8", x=48.8, y=31.6, rot=90, side="B"),
    dict(op="route", net="R_MTEMP", a=("pad", "D8", "3"), b=("pad", "R53", "2"), layers=ALL, layer_cost={"In4.Cu": 1.5}, w=0.15, margin=3.0, max_ratio=4.0),
    dict(op="route", net="+3V3", a=("pad", "D8", "2"), b=("pad", "R53", "1"), layers=ALL, layer_cost={"In4.Cu": 1.5}, w=0.2, margin=3.0, max_ratio=4.0),
    dict(op="drop", pad=("D8", "1"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
