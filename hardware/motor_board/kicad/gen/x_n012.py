# move R43 by 2.50 rot +90 any
EDITS = [
    dict(op="rip_ref", ref="R43"),
    dict(op="move", ref="R43", x=54.45, y=32.5, rot=270.0, side="F"),
    dict(op="route", net="+3V3", a=("pad", "R43", "1"), b=('pt', 55.13, 33.7, 'B.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.2, margin=6.0, max_ratio=4.0),
    dict(op="route", net="W_NTC", a=("pad", "R43", "2"), b=('pt', 57.6, 18.8, 'In3.Cu'), layers=['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={"In4.Cu": 1.5, "In3.Cu": 2.0}, w=0.15, margin=6.0, max_ratio=4.0),
]
