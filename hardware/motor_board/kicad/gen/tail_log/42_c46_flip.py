"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# C46 (L_VS decoupling) flipped to the bottom at U1's NE corner: its GND pad was on an unanchored F fill island;
# on B it sits in the main fill.  Its L_VS side stays open (the U11 / J2 knot).
EDITS = [
    dict(op="rip_ref", ref="C46"),
    dict(op="move", ref="C46", x=43.1, y=23.6, rot=90.0, side="B"),
    dict(op="route", net="/sensors/L_VS", a=("pad", "C46", "1"), b=('pad', 'U11', '1'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C46", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
