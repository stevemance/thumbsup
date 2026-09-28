"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
EDITS += [dict(e, op="why", margin=8.0, w=(0.2 if e["net"] in ("+3V3", "+5V") else 0.127)) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "19_input_drc.json", skip=("GND",))]
EDITS = [e for e in EDITS if e["op"] != "why"]
EDITS += [dict(op="route", net="+3V3", a=("via", 39.2, 21.55), b=("via", 42.95, 18.8), layers=[L4, L3], w=0.15, margin=4.0)]
EDITS += [dict(e, margin=8.0, w=0.15) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "19_input_drc.json", only=("+3V3",))]
EDITS += [dict(e, margin=8.0, w=0.15, ignore_pours=True, tag="ip " + e["net"]) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "19_input_drc.json", only=("+3V3",))]
EDITS = []
from l4stitch import stitch  # noqa: E402
EDITS += stitch("19_l4_islands.json", per_pair=4, tree=False, max_ratio=2.5, layers=["In3.Cu", "F.Cu", "B.Cu"])
