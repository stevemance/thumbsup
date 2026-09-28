"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# C410 (U4's third VM bulk cap, 20 mm away since placement): 0.15 mm link via L3/L5; in R402's slow RC filter a
# ~70 mOhm series path is harmless (C410 alone: ~0.3 us vs the filter's ~1.6 us)
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={'In4.Cu': 2.0}, margin=5.0, max_ratio=4.0)
EDITS = [
    dict(op="rip", box=(57.425, 31.25, 58.425, 32.25), nets=["R_S1"], layers=["In2.Cu"], reroute=RR, cross=True),
    dict(op="vip", pad=("C410", "1"), off=(-0.55, 0.6), d=0.4, drill=0.2),
    dict(op="route", net="/drive_right/R_VM", a=("via", 57.925, 31.75), b=('pad', 'C408', '1'), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
]
