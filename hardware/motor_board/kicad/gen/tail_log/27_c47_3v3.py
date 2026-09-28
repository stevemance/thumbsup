"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={"In4.Cu": 2.0}, margin=5.0, max_ratio=4.0)
EDITS = [
    # C47 (U9 VCC decap) +3V3: via at its pad edge; MB_RX's L4 run there re-laid
    dict(op="rip", box=(32.9, 24.1, 33.2, 24.5), nets=["/mcu/MB_RX"], layers=["In3.Cu"], reroute=RR),
    dict(op="vip", pad=("C47", "1"), off=(0.3, 0.35), d=0.4, drill=0.2),
    dict(op="route", net="+3V3", a=("via", 31.48, 24.5), b=("pt", 30.7, 22.25, "B.Cu"), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.2, margin=3.0, max_ratio=4.0),
    dict(op="route", net="+3V3", a=("pad", "C47", "1"), b=("pt", 33.3, 24.1, "F.Cu"), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.2, margin=3.0, max_ratio=4.0),
]
