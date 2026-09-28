# move C46 by 0.00 rot +180 pads
EDITS = [
    dict(op="rip_ref", ref="C46"),
    dict(op="move", ref="C46", x=42.85, y=24.1, rot=180.0, side="F"),
    dict(op="route", net="/sensors/L_VS", a=("pad", "C46", "1"), b=('pad', 'U11', '1'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C46", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
