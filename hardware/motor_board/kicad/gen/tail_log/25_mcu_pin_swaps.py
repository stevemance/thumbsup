"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
# MCU pin swaps (design/motor_board.py, mcu_pinmap.md): left encoder A/B onto PB4 / PB5 (TIM3_CH1 / CH2, either
# order: the count sign is a firmware constant), R_nCS PB4 -> PA11, INA_nCS PA11 -> PB8 (BOOT0 pin: R61 removed,
# nSWBOOT0 = 0 / nBOOT0 = 1 option bytes; R12 keeps INA_nCS high), PC6 unused.  Each moved net keeps a fan-out
# that already existed: L_S2 takes R_nCS's pin-57 via beside U9.5, R_nCS takes INA_nCS's pin-45 stub beside its
# own L3 lane via.
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
K = dict(layers=ALL5, layer_cost={"In4.Cu": 4.0}, margin=6.0, max_ratio=3.0, w=0.127)
EDITS = [
    dict(op="rip", box=(30.95, 31.35, 31.35, 31.75), nets=["INA_nCS"]),   # its old via beside pin 45
    dict(op="rip", box=(32.2, 28.75, 33.0, 32.5), nets=["R_nCS"], layers=["F.Cu"]),
    dict(op="rip", box=(25.3, 22.6, 31.45, 31.8), nets=["INA_nCS"], layers=["In3.Cu", "B.Cu"]),
    dict(op="rip_ref", ref="R61"),
    dict(op="del_fp", ref="R61"),
    dict(op="swap_pin", ref="U1", pad="57", net="L_S2", box=(29.3, 25.5, 32.6, 28.8)),
    dict(op="swap_pin", ref="U1", pad="58", net="L_S1", box=(29.3, 25.0, 30.7, 25.5)),
    dict(op="swap_pin", ref="U1", pad="38", net="unconnected-(U1-PC6-Pad38)", box=(36.4, 31.0, 37.1, 32.5)),
    dict(op="swap_pin", ref="U1", pad="45", net="R_nCS", box=(32.9, 31.0, 33.4, 32.9)),
    dict(op="swap_pin", ref="U1", pad="61", net="INA_nCS", box=(27.9, 23.5, 30.7, 24.0)),
    dict(op="route", net="L_S2", a=("via", 32.45, 28.7), b=("pad", "U9", "5"), **K),
    dict(op="route", net="R_nCS", a=("pt", 33.05, 32.75, "B.Cu"), b=("via", 33.75, 32.8), **K),
    dict(op="route", net="L_S1", a=("pad", "U9", "7"), b=("pad", "U1", "58"), **K),
    dict(op="route", net="INA_nCS", a=("pad", "U1", "61"), b=("pt", 25.3, 22.55, "In3.Cu"), **dict(K, margin=6.0, max_ratio=4.0)),
]
