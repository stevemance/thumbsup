"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
# L_VSRC (hall supply source, JP1.2 -> U11.4/5, a few mA): U11.5-side via in the pad, JP1.2 via 0.5 mm off, 2.7 mm L5 jumper
EDITS = [
    dict(op='via', c=(38.838, 24.1), net='/sensors/L_VSRC', d=0.4, drill=0.2),
    dict(op='via', c=(40.25, 21.75), net='/sensors/L_VSRC', d=0.4, drill=0.2),
    dict(op='track', pts=[(40.599999999999994, 22.099999999999994), (40.25, 21.75)], layer='F.Cu', net='/sensors/L_VSRC', w=0.15),
    dict(op='route', net='/sensors/L_VSRC', a=('via', 38.838, 24.1), b=('via', 40.25, 21.75), layers=['In4.Cu'], w=0.15, margin=4.0, max_ratio=5.0),
]
