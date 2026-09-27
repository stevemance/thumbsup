"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L4 = "In3.Cu"

EDITS = [
    # GND pour islands (F/B fills) with pads but no via to the planes: a stitch via inside the island where one fits,
    # else the pad dropped
    dict(op="via", net="GND", c=(48.015, 21.094)),
    dict(op="via", net="GND", c=(39.384, 34.195)),
]
for _r, _n in [("C30", "2"), ("C112", "2"), ("R21", "2"), ("TP12", "1"), ("C111", "2"), ("C45", "2"),
               ("C64", "2"), ("U1", "47"), ("C61", "2"), ("R61", "2"), ("R40", "2"), ("C50", "2"), ("U1", "15"), ("U7", "7")]:
    EDITS.append(dict(op="drop", pad=(_r, _n), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2))
