"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

ALL = ["F.Cu", "B.Cu", "In2.Cu", "In4.Cu", "In3.Cu"]
RR = dict(layers=ALL, layer_cost={"In4.Cu": 1.0, "In3.Cu": 1.5}, margin=8.0, max_ratio=6.0)
# L_H1: J2.3 sits under U9's pad column with no legal via; lift one W_EN B run (J2.3 side) and one W_INLB_M L4 run
# (R54 side), vias at the pad edges (filled + capped, FAB.md), 6.4 mm L5 jumper (slow hall input)
EDITS = [
    dict(op="rip", box=(32.6, 29.8, 33.6, 30.8), nets=["W_EN"], layers=["B.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(32.8, 24.75, 33.8, 25.75), nets=["W_INLB_M"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="vip", pad=("J2", "3"), off=(0.3, 0.4)),
    dict(op="vip", pad=("R54", "1"), off=(-0.25, -0.15)),
    dict(op="route", net="/sensors/L_H1", a=("via", 33.1, 30.3), b=("via", 33.29, 25.25), layers=["In4.Cu"], w=0.15, margin=3.0, max_ratio=6.0),
]
