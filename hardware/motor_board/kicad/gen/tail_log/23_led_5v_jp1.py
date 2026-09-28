"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
# power LED D3 + its 1 k R62 into the band beside the +5V bridge (R62 sat 35 mm from D3, at U4); D3 stays on the
# rear edge, top side (visible)
LED = [
    dict(op="rip_ref", ref="R62"), dict(op="rip_ref", ref="D3"),
    dict(op="rip", box=(0, 0, 85, 35), nets=["/mcu/LED_A"]),
    dict(op="move", ref="R62", x=46.6, y=32.2, rot=90, side="F"),
    dict(op="move", ref="D3", x=48.7, y=32.2, rot=180, side="F"),
    dict(op="track", net="/mcu/LED_A", layer="F.Cu", pts=[(46.6, 31.69), (46.6, 31.75), (47.05, 32.2), (47.913, 32.2)], w=0.2),
    dict(op="track", net="+5V", layer="F.Cu", pts=[(46.6, 32.71), (46.6, 33.85)], w=0.3),
    dict(op="drop", pad=("D3", "1"), net="GND", margin=2.0, w=0.3, via=0.45, drill=0.25),
]

# +5V to JP1 (left sensor supply select, a few mA): W_VA's hop over U1's east pins lifted (re-routed on L5: an
# analog sense line between planes), C46's GND stub re-made to the one legal via spot
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
K = dict(layers=ALL5, layer_cost={"In4.Cu": 4.0}, margin=8.0, max_ratio=2.5)
EDITS = LED + [
    dict(op="rip", box=(39.8, 22.2, 44.5, 23.4), nets=["W_VA"], layers=["F.Cu"], reroute=dict(K, max_ratio=4.0)),
    dict(op="rip", box=(43.2, 23.8, 43.9, 24.5), nets=["GND"], layers=["F.Cu"]),
    dict(op="via", net="GND", c=(44.3, 25.15), d=0.4, drill=0.2),
    dict(op="route", net="GND", a=("pad", "C46", "2"), b=("via", 44.3, 25.15), layers=["F.Cu"], w=0.2, margin=1.5),
    dict(op="route", net="+5V", a=("pad", "TP11", "1"), b=("pad", "JP1", "3"), w=0.2, **K),
    dict(op="route", net="+5V", a=("pad", "JP2", "3"), b=("pad", "TP11", "1"), w=0.3, **dict(K, max_ratio=3.0)),
    dict(op="route", net="+5V", a=("pad", "R20", "1"), b=("pad", "C29", "1"), w=0.2, **dict(K, max_ratio=3.0)),
]
