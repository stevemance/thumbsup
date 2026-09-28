# move R113 by 3.75 rot +0 any
EDITS = [
    dict(op="rip_ref", ref="R113"),
    dict(op="move", ref="R113", x=45.65, y=29.4, rot=90.0, side="B"),
    dict(op="route", net="/sensors/L_TEMPJ", a=("pad", "R113", "1"), b=('pt', 42.9, 32.0, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
    dict(op="route", net="L_MTEMP", a=("pad", "R113", "2"), b=('pt', 42.2, 26.75, 'F.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
]
