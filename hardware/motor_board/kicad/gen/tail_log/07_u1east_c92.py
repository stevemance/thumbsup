"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
    # U1 east pins 18-20 (W_VA / W_VB / W_NTC) to their filter caps: R_SOC_F looped from R82 (F) up to C92 (B, at the
    # pins) and fenced the corridor. C92 goes to F under R82, the loop and C92 GND drop are lifted, so are GND stubs in
    # the corridor, then the three pins are routed
    dict(op="rip", box=(40.9, 19.5, 43.1, 25.6), nets=["/mcu/R_SOC_F"]),
    dict(op="move", ref="C92", x=40.65, y=26.6, rot=-90, side="F"),
    dict(op="rip", box=(41.5, 22.0, 45.3, 23.1), nets=["W_VA"], layers=["B.Cu"]),
    dict(op="rip", box=(43.6, 20.9, 44.0, 21.9), nets=["GND"]),
    dict(op="rip", box=(44.1, 22.1, 44.4, 22.4), nets=["GND"]),
    # C42's GND stub looped west round C42.1 to a via at (44.15, 18.9): it takes the nearer C41 drop via instead
    dict(op="rip", box=(44.1, 18.8, 45.75, 20.9), nets=["GND"], layers=["B.Cu"]),
    dict(op="track", net="GND", layer="B.Cu", w=0.25, pts=[(45.68, 20.25), (45.605, 20.92)]),
    dict(op="route", net="W_VB", a=("pad", "U1", "19"), b=("pad", "C42", "1"), w=0.15, margin=3.0, layers=["B.Cu"]),
    dict(op="route", net="W_VA", a=("pad", "U1", "18"), b=("pad", "C41", "1"), w=0.15, margin=3.0),
    dict(op="route", net="/mcu/R_SOC_F", a=("pad", "R82", "2"), b=("pad", "C92", "1"), w=0.15, margin=2.0),
]
