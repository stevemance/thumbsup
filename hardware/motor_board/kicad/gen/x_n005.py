# move C91 by 0.56 rot +90 pads
EDITS = [
    dict(op="rip_ref", ref="C91"),
    dict(op="move", ref="C91", x=38.75, y=33.15, rot=90.0, side="F"),
    dict(op="route", net="/mcu/R_SOB_F", a=("pad", "C91", "1"), b=('pad', 'U1', '35'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C91", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
