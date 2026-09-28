"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# SWDIO: via in U1.49's pad (filled, capped), SWCLK B / SPI_MOSI, SPI_SCK L3 runs lifted and re-laid
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
RR = dict(layers=ALL5, layer_cost={'In4.Cu': 2.0}, margin=5.0, max_ratio=4.0)
EDITS = [
    dict(op="rip", box=(29.475, 29.3, 30.475, 30.3), nets=["/mcu/SWCLK"], layers=["B.Cu"], reroute=RR, cross=True),
    dict(op="rip", box=(29.475, 29.3, 30.475, 30.3), nets=["SPI_MOSI"], layers=["In2.Cu"], reroute=RR, cross=True),
    dict(op="rip", box=(29.475, 29.3, 30.475, 30.3), nets=["SPI_SCK"], layers=["In2.Cu"], reroute=RR, cross=True),
    dict(op="vip", pad=("U1", "49"), off=(0.15, 0.05), d=0.4, drill=0.2),
    dict(op="route", net="/mcu/SWDIO", a=("via", 29.975, 29.8), b=('pad', 'J1', '9'), layers=["F.Cu", "B.Cu", "In2.Cu", "In4.Cu"], layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
    dict(op="route", net="/mcu/SWDIO", a=("via", 29.975, 29.8), b=("pad", "TP2", "1"), layers=["F.Cu", "B.Cu", "In2.Cu", "In4.Cu"], layer_cost={"In4.Cu": 2.0}, w=0.15, margin=8.0, max_ratio=3.0),
]
