"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
]
_RS = ["/sensors/R_H1", "/sensors/R_H1B", "/sensors/R_H2", "/sensors/R_H2B", "/sensors/R_H3", "/sensors/R_H3B",
       "/sensors/R_VS", "/sensors/R_TEMPJ", "/sensors/R_VSRC"]
EDITS += [
    # right sensors: J3 fans out in every direction (pull-ups west and north, filters above, U10 east); the whole set is
    # lifted in the region and routed together, rip-up allowed among them
    dict(op="rip", box=(43.0, 21.5, 63.5, 35.0), nets=_RS),
]
_PAIRS = [("/sensors/R_H1", ("J3", "3"), ("R57", "1")), ("/sensors/R_H1", ("J3", "3"), ("R114", "1")), ("/sensors/R_H2", ("J3", "4"), ("R115", "1")),
          ("/sensors/R_H3", ("J3", "5"), ("R116", "1")), ("/sensors/R_H1B", ("R114", "2"), ("C114", "1")),
          ("/sensors/R_H1B", ("C114", "1"), ("U10", "1")), ("/sensors/R_H2B", ("R115", "2"), ("U10", "3")),
          ("/sensors/R_H2B", ("U10", "3"), ("C115", "1")), ("/sensors/R_H3B", ("R116", "2"), ("U10", "6")),
          ("/sensors/R_H3B", ("U10", "6"), ("C116", "1")), ("/sensors/R_VSRC", ("U12", "5"), ("U12", "4")),
          ("/sensors/R_VSRC", ("U12", "5"), ("C48", "1")), ("/sensors/R_VSRC", ("C48", "1"), ("JP2", "2")),
          ("/sensors/R_VS", ("U12", "1"), ("C49", "1")), ("/sensors/R_VS", ("J3", "1"), ("U12", "1")),
          ("/sensors/R_TEMPJ", ("J3", "6"), ("R117", "1")),
          ("/sensors/R_H2", ("J3", "4"), ("R58", "1")), ("/sensors/R_H3", ("J3", "5"), ("R59", "1"))]
EDITS += [dict(op="route", net=n, a=("pad",) + a, b=("pad",) + b, w=0.15, margin=6.0, soft=True) for n, a, b in _PAIRS]
# via in pad (filled + capped, FAB.md) for boxed-in passive pads left without a tie to their plane / pour; offsets
# searched inside the pad for full clearance on every layer (most candidates have none: the opposite side or L3/L4)
EDITS += [dict(op="vip", pad=("C112", "2"), off=(0.12, -0.26)), dict(op="vip", pad=("C74", "1"), off=(-0.28, 0.215)),
          dict(op="vip", pad=("C62", "1"), off=(-0.255, -0.16))]
