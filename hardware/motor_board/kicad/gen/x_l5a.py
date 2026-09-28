ALL = ["F.Cu", "B.Cu", "In4.Cu", "In3.Cu"]
LC = {"In4.Cu": 1.0, "In3.Cu": 2.0}
EDITS = [
    dict(op="route", net="/sensors/L_H1", a=("pt", 33.54, 25.40, "F.Cu"), b=("pad", "J2", "3"), layers=ALL, layer_cost=LC, w=0.15, margin=4.0, max_ratio=6.0),
    dict(op="route", net="L_S3", a=("pt", 33.50, 23.30, "In3.Cu"), b=("pad", "U9", "2"), layers=ALL, layer_cost=LC, w=0.15, margin=4.0, max_ratio=6.0),
    dict(op="route", net="L_MTEMP", a=("pt", 41.30, 27.65, "F.Cu"), b=("pt", 34.85, 24.60, "F.Cu"), layers=ALL, layer_cost=LC, w=0.15, margin=4.0, max_ratio=6.0),
    dict(op="route", net="L_nCS", a=("pad", "U1", "41"), b=("pt", 28.20, 30.25, "F.Cu"), layers=ALL, layer_cost=LC, w=0.15, margin=4.0, max_ratio=6.0),
    dict(op="route", net="/mcu/SWDIO", a=("pt", 29.97, 29.80, "In4.Cu"), b=("pad", "TP2", "1"), layers=ALL, layer_cost=LC, w=0.15, margin=4.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VS", a=("pad", "U11", "1"), b=("pad", "J2", "1"), layers=ALL, layer_cost=LC, w=0.25, margin=4.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VS", a=("pad", "U11", "1"), b=("pad", "C46", "1"), layers=ALL, layer_cost=LC, w=0.25, margin=4.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VSRC", a=("pt", 38.84, 24.10, "F.Cu"), b=("pt", 40.60, 22.10, "F.Cu"), layers=ALL, layer_cost=LC, w=0.25, margin=4.0, max_ratio=6.0),
]
