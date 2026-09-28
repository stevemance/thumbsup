"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={"In4.Cu": 1.5}, margin=7.0, max_ratio=5.0)
EDITS = [
    # U3 pin 23 (nSLEEP, +3V3): via just below the pin, tied on B / L5 to pin 28's +3V3 via; SWCLK's L4 run there re-laid
    dict(op="rip", box=(20.7, 32.55, 21.6, 33.45), nets=["/mcu/SWCLK"], layers=["In3.Cu"], reroute=RR, cross=True),
    dict(op="track", net="+3V3", layer="F.Cu", pts=[(21.25, 32.4), (21.25, 32.9), (21.15, 33.0)], w=0.15),
    dict(op="via", net="+3V3", c=(21.15, 33.0), d=0.4, drill=0.2),
    dict(op="route", net="+3V3", a=("via", 21.15, 33.0), b=("via", 23.75, 34.1), layers=["B.Cu", "In4.Cu"],
         layer_cost={"In4.Cu": 1.5}, w=0.15, margin=2.5, max_ratio=4.0),
]
