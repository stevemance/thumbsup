"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# INA_nCS (now PB8, pin 61): via at the pin with MB_TX's L4 run lifted and re-laid
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={'In4.Cu': 1.5}, margin=9.0, max_ratio=6.0)
EDITS = [
    dict(op="rip", box=(28.375, 23.25, 29.375, 24.25), nets=["/mcu/MB_TX"], layers=["In3.Cu"], cross=True),
    dict(op="vip", pad=("U1", "61"), off=(-0.95, 0.0), d=0.4, drill=0.2),
    dict(op="route", net="INA_nCS", a=("via", 28.875, 23.75), b=('pt', 25.3, 22.55, 'In3.Cu'), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
]
EDITS += [dict(op="route", net="/mcu/MB_TX", a=("pt", 24.0, 23.7, "F.Cu"), b=("pt", 31.1, 23.7, "In3.Cu"), layers=ALL5, layer_cost={"In4.Cu": 1.5}, w=0.15, margin=9.0, max_ratio=6.0)]
# L4 3V3 fill islands after it: short stitches (l4stitch)
from l4stitch import stitch  # noqa: E402
EDITS += stitch("30_l4_islands.json", per_pair=4, tree=False, max_ratio=2.5, layers=["In3.Cu", "F.Cu", "B.Cu", "In4.Cu"], layer_cost={"In4.Cu": 2.0})
