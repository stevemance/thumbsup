ALL = ["F.Cu", "B.Cu", "In2.Cu", "In4.Cu", "In3.Cu"]
RR = dict(layers=ALL, layer_cost={"In4.Cu": 1.0, "In3.Cu": 1.5}, margin=12.0, max_ratio=10.0)
L5 = ["In4.Cu"]
EDITS = [
    dict(op="rip", box=(32.6, 29.8, 33.6, 30.8), nets=["W_EN"], layers=["B.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(29.75, 30.2, 30.75, 31.2), nets=["SPI_MOSI"], layers=["In2.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(29.75, 30.2, 30.75, 31.2), nets=["W_EN"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(32.8, 24.75, 33.8, 25.75), nets=["W_INLB_M"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="rip", box=(36.16, 23.65, 37.16, 24.65), nets=["/mcu/MB_TX"], layers=["In3.Cu"], cross=True, reroute=RR),
    dict(op="vip", pad=("J2", "3"), off=(0.3, 0.4)),
    dict(op="vip", pad=("R54", "1"), off=(-0.25, -0.15)),
    dict(op="vip", pad=("J2", "1"), off=(-0.55, 0.8)),
    dict(op="vip", pad=("U11", "1"), off=(-0.5, 0.05)),
    dict(op="route", net="/sensors/L_H1", a=("via", 33.1, 30.3), b=("via", 33.29, 25.25), layers=L5, w=0.15, margin=3.0, max_ratio=6.0),
    dict(op="route", net="/sensors/L_VS", a=("via", 30.25, 30.7), b=("via", 36.6625, 24.15), layers=["In3.Cu", "In4.Cu"], w=0.2, margin=4.0, max_ratio=8.0),
    dict(op="route", net="/sensors/L_VS", a=("pad", "U11", "1"), b=("pad", "C46", "1"), layers=ALL, layer_cost={"In4.Cu": 1.0, "In3.Cu": 1.5}, w=0.25, margin=4.0, max_ratio=6.0),
]
