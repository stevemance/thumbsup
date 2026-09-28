"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# via-at-pad with one or two lifted runs (genvip): VBAT_SW sense at R2, SPI_SCK at U7
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={'In4.Cu': 2.0}, margin=5.0, max_ratio=4.0)
EDITS = []
# /power/VBAT_SW ('pad', 'R2', '1') lifting (('+3V3', 'In3.Cu'),)
EDITS += [
    dict(op="rip", box=(22.24, 4.55, 23.24, 5.55), nets=["+3V3"], layers=["In3.Cu"], reroute=RR, cross=True),
    dict(op="vip", pad=("R2", "1"), off=(-0.25, -0.1), d=0.4, drill=0.2),
    dict(op="route", net="/power/VBAT_SW", a=("via", 22.74, 5.05), b=('pad', 'RS4', '1'), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
]
# SPI_SCK ('pad', 'U7', '5') lifting (('/mcu/VBAT_SNS', 'In3.Cu'), ('INA_nCS', 'B.Cu'))
EDITS += [
    dict(op="rip", box=(21.35, 10.9, 22.35, 11.9), nets=["/mcu/VBAT_SNS"], layers=["In3.Cu"], reroute=RR, cross=True),
    dict(op="rip", box=(21.35, 10.9, 22.35, 11.9), nets=["INA_nCS"], layers=["B.Cu"], reroute=RR, cross=True),
    dict(op="vip", pad=("U7", "5"), off=(-0.15, 0.3), d=0.4, drill=0.2),
    dict(op="route", net="SPI_SCK", a=("via", 21.85, 11.4), b=('pt', 29.7, 28.25, 'In2.Cu'), layers=ALL5, layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
]
