"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.2}, margin=10.0, max_ratio=8.0)
# W_INLA_M (U1.21): via just outside the pad (a W_VA L5 run lifted), then mostly L5 through the area cell C left, to U6's side
EDITS = [
    dict(op='rip', box=(41.7, 23.8, 42.55, 24.7), nets=['W_VA'], layers=['In4.Cu'], cross=True, reroute=RR),
    dict(op='via', c=(42.125, 24.25), net='W_INLA_M', d=0.4, drill=0.2),
    dict(op='track', pts=[(41.175, 24.25), (42.125, 24.25)], layer='B.Cu', net='W_INLA_M', w=0.15),
    dict(op='route', net='W_INLA_M', a=('via', 42.125, 24.25), b=('pt', 32.5, 11.3, 'B.Cu'), layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.3, 'In2.Cu': 1.5}, w=0.15, margin=6.0, max_ratio=4.0),
]
