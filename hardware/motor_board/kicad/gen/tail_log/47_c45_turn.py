"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.3}, margin=8.0, max_ratio=6.0)
# C45 (L_VSRC decoupling) turned 90 deg, 0.75 mm north: its GND pad gets a via to the planes (was on a fenced F island);
# a W_NFAULT F piece re-laid around it
EDITS = [
    dict(op='rip', box=(37.3, 18.4, 39.0, 19.8), nets=['W_nFAULT'], layers=['F.Cu'], cross=True, reroute=RR),
    dict(op="rip_ref", ref="C45"),
    dict(op="move", ref="C45", x=38.35, y=19.1, rot=90.0, side="F"),
    dict(op="route", net="/sensors/L_VSRC", a=("pad", "C45", "1"), b=('pt', 40.55, 19.5, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C45", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
