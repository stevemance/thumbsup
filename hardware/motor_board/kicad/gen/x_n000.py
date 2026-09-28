# move C111 by 2.85 rot +0 any
EDITS = [
    dict(op="rip_ref", ref="C111"),
    dict(op="move", ref="C111", x=27.4, y=23.65, rot=180.0, side="B"),
    dict(op="route", net="/sensors/L_H2B", a=("pad", "C111", "1"), b=('pt', 28.6, 26.0, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="drop", pad=("C111", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2),
]
