"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
# +5V to J1 (compute board feed, <= 0.45 A): the only path is an L5 trunk (0.35 mm, ~36 mm) near the rear edge,
# y ~32.5 from x 50.8 to 18.2; the L5 strip south of it is stitched by the GND via rows at y 33.2 / 34.1
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
EDITS = [dict(op="route", net="+5V", a=("pad", "TP11", "1"), b=("pad", "J1", "1"), layers=ALL5, layer_cost={"In4.Cu": 6.0},
              margin=12.0, max_ratio=2.6, w=0.35)]
