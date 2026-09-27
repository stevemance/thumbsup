"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L4 = "In3.Cu"

EDITS = [
]
from tail_auto import auto  # noqa: E402
EDITS += [dict(e, ignore_pours=True) for e in auto(only=("+5V",), w=0.3, margin=10.0)]
EDITS += [dict(e, ignore_pours=True) for e in auto(only=("/drive_right/R_VM", "/drive_left/L_VM", "/power/BAT_IN", "/power/VBAT_SW"), w=0.4, margin=10.0)]
EDITS += [dict(e, ignore_pours=True) for e in auto(only=("+3V3",), w=0.25, margin=6.0)]
