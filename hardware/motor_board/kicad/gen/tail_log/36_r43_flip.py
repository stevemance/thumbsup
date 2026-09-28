"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# R43 (weapon NTC pull-up) flipped to the top at the band's rear: W_NTC over L5 (a slow NTC node, C44 filters it at the MCU);
# its old pad was a +3V3 B-bridge junction, re-joined
EDITS = [
    dict(op="rip_ref", ref="R43"),
    dict(op="move", ref="R43", x=54.45, y=32.5, rot=270.0, side="F"),
    dict(op="route", net="+3V3", a=("pad", "R43", "1"), b=('pt', 55.13, 33.7, 'B.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.2, margin=6.0, max_ratio=4.0),
    dict(op="route", net="W_NTC", a=("pad", "R43", "2"), b=('pt', 57.6, 18.8, 'In3.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="route", net="+3V3", a=("pt", 56.0, 33.0, "B.Cu"), b=("pt", 57.95, 33.0, "B.Cu"), layers=["B.Cu", "In4.Cu"], w=0.25, margin=1.5, max_ratio=3.0),
]
