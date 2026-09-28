ALL = ["F.Cu", "B.Cu", "In2.Cu", "In4.Cu", "In3.Cu"]
RR = dict(layers=ALL, layer_cost={"In4.Cu": 1.0, "In3.Cu": 1.5}, margin=8.0, max_ratio=6.0)
L5 = ["F.Cu", "In4.Cu"]
EDITS = [
    dict(op="rip", box=(32.6, 29.8, 33.6, 30.8), nets=["W_EN"], layers=["B.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(30.5, 28.8, 31.5, 29.8), nets=["/mcu/SWCLK"], layers=["B.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(32.8, 24.75, 33.8, 25.75), nets=["W_INLB_M"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(36.16, 23.65, 37.16, 24.65), nets=["/mcu/MB_TX"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="route", net="/sensors/L_H1", a=("pad", "J2", "3"), b=("pt", 33.54, 25.40, "F.Cu"), layers=L5, layer_cost={"In4.Cu": 1.0}, w=0.15, margin=3.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VS", a=("pad", "J2", "1"), b=("pad", "U11", "1"), layers=L5, layer_cost={"In4.Cu": 1.0}, w=0.25, margin=3.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VS", a=("pad", "U11", "1"), b=("pad", "C46", "1"), layers=ALL, layer_cost={"In4.Cu": 1.0, "In3.Cu": 1.5}, w=0.25, margin=4.0, max_ratio=6.0),
]
