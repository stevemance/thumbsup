# move JP1 by 0.25 rot +0 any
EDITS = [
    dict(op="rip_ref", ref="JP1"),
    dict(op="move", ref="JP1", x=40.35, y=22.1, rot=0.0, side="F"),
    dict(op="route", net="+3V3", a=("pad", "JP1", "1"), b=('pt', 38.9, 22.9, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.2, margin=6.0, max_ratio=4.0),
    dict(op="route", net="/sensors/L_VSRC", a=("pad", "JP1", "2"), b=('pt', 40.6, 20.95, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="route", net="+5V", a=("pad", "JP1", "3"), b=('pt', 43.3, 23.5, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.2, margin=6.0, max_ratio=4.0),
]
