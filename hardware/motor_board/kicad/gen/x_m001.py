# move U11 by 0.25 rot +0 pads
EDITS = [
    dict(op="rip_ref", ref="U11"),
    dict(op="move", ref="U11", x=38.25, y=24.75, rot=0.0, side="F"),
    dict(op="route", net="/sensors/L_VS", a=("pad", "U11", "1"), b=('pad', 'C46', '1'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("U11", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
    dict(op="route", net="/sensors/L_VSRC", a=("pad", "U11", "4"), b=('pad', 'JP1', '2'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="route", net="/sensors/L_VSRC", a=("pad", "U11", "5"), b=('pad', 'JP1', '2'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
]
