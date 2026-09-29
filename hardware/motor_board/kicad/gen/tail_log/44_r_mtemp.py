"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.0}, margin=8.0, max_ratio=8.0)
# R_MTEMP (U1.6, ADC): pin 5 (L_MTEMP) and pin 6 get staggered inward vias under U1 (pin 5's moved from y 21.55 to 22.0,
# its F clamp branch re-joined; a W_INLB_M via there re-placed); pin 6 -> L4, 11 mm, to the R_MTEMP node at R117 / D8
EDITS = [
    dict(op='rip', box=(33.6, 21.2, 35.2, 23.9), nets=['L_MTEMP'], layers=['B.Cu']),
    dict(op='rip', box=(33.6, 22.2, 35.6, 24.3), nets=['W_INLB_M'], cross=True, reroute=RR),
    dict(op='rip', box=(33.8, 21.35, 34.2, 21.75), nets=['L_MTEMP']),
    dict(op='track', pts=[(33.75, 20.325), (33.75, 22.0)], layer='B.Cu', net='L_MTEMP', w=0.15),
    dict(op='via', c=(33.75, 22.0), net='L_MTEMP', d=0.4, drill=0.2),
    dict(op='track', pts=[(34.0, 21.3), (34.0, 21.75), (33.75, 22.0)], layer='F.Cu', net='L_MTEMP', w=0.15),
    dict(op='route', net='L_MTEMP', a=('via', 33.75, 22.0), b=('via', 35.0, 23.8), layers=['In4.Cu', 'In3.Cu'], layer_cost={'In3.Cu': 2.0}, w=0.15, margin=2.0, max_ratio=4.0),
    dict(op='track', pts=[(34.25, 20.325), (34.25, 22.35)], layer='B.Cu', net='R_MTEMP', w=0.15),
    dict(op='via', c=(34.25, 22.35), net='R_MTEMP', d=0.4, drill=0.2),
    dict(op='route', net='R_MTEMP', a=('via', 34.25, 22.35), b=('via', 44.05, 24.6), layers=['In3.Cu', 'In4.Cu'], layer_cost={'In4.Cu': 1.2}, w=0.15, margin=5.0, max_ratio=4.0),
]
