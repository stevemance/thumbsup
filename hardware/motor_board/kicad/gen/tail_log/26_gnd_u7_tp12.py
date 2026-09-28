"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
# GND pieces: U7 (INA239) pin 7 and TP12: a via each where a single signal run was lifted (and re-laid)
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
EDITS = []
EDITS += [
    # U7 (INA239) pin 7 GND: a via just north of the pin; DRV_OFF's F run from TP8 and the L4 +3V3 run over the
    # spot are re-laid around it (L4 is the 3V3 fill layer)
    dict(op="rip", box=(21.55, 5.1, 22.9, 6.3), nets=["DRV_OFF"], layers=["F.Cu"]),
    dict(op="rip", box=(21.3, 5.9, 23.6, 6.4), nets=["+3V3"], layers=["In3.Cu"], reroute=dict(layers=["In3.Cu", "B.Cu", "F.Cu"], margin=4.0, max_ratio=4.0)),
    dict(op="track", net="GND", layer="B.Cu", pts=[(22.5, 6.3), (22.5, 5.8)], w=0.2),
    dict(op="via", net="GND", c=(22.5, 5.8), d=0.4, drill=0.2),
    dict(op="route", net="DRV_OFF", a=("pad", "TP8", "1"), b=("pt", 24.3, 6.25, "F.Cu"), layers=["F.Cu", "B.Cu", "In3.Cu", "In4.Cu"],
         layer_cost={"In4.Cu": 3.0}, margin=4.0, max_ratio=4.0, w=0.15),
]
EDITS += [
    dict(op="rip", box=(27.0, 24.95, 27.9, 25.849999999999998), nets=["L_INHA"], layers=["In2.Cu"],
         reroute=dict(layers=ALL5, layer_cost={"In4.Cu": 3.0}, margin=5.0, max_ratio=4.0)),
    dict(op="via", net="GND", c=(27.45, 25.4), d=0.4, drill=0.2),
    dict(op="route", net="GND", a=("pad", "TP12", "1"), b=("via", 27.45, 25.4), layers=["F.Cu"], w=0.2, margin=2.0),
]
