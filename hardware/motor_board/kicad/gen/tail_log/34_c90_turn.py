"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# C90 (R_SOA_F filter cap) turned 180: its GND pad drops a via; R_SOA_F re-laid outside the C64 / C73 GND island
EDITS = [
    dict(op="rip_ref", ref="C90"),
    dict(op="move", ref="C90", x=41.25, y=33.4, rot=180.0, side="B"),
    dict(op="route", net="/mcu/R_SOA_F", a=("pad", "C90", "1"), b=('pt', 43.4, 33.4, 'In2.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C90", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
    dict(op="route", net="/mcu/R_SOA_F", a=("pt", 38.75, 32.77, "B.Cu"), b=("pt", 41.25, 33.65, "In2.Cu"), layers=["F.Cu", "B.Cu", "In2.Cu", "In4.Cu", "In3.Cu"], layer_cost={"In4.Cu": 1.0, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=6.0, avoid=[["B.Cu", 39.6, 31.1, 44.23, 34.5, "tracks"]]),
]
