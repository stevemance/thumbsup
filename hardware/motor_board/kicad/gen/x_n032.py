# move R59 by 3.89 rot +0 any
EDITS = [
    dict(op="rip_ref", ref="R59"),
    dict(op="move", ref="R59", x=72.75, y=20.7, rot=0.0, side="F"),
    dict(op="route", net="/sensors/R_H3", a=("pad", "R59", "1"), b=('pt', 62.5, 29.35, 'B.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="route", net="+3V3", a=("pad", "R59", "2"), b=('pt', 72.5, 21.5, 'B.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.2, margin=6.0, max_ratio=4.0),
]
