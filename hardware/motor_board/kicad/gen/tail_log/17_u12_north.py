"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
    # W_INLB had a second, parallel run on B (via at 45.7 / 22.5 to U2) beside its L4 lane: the B run goes, it fenced
    # the U12 / JP2 / C48 corridor (R_VSRC)
    dict(op="rip", box=(45.5, 22.3, 62.0, 26.8), nets=["/weapon/W_INLB"], layers=[B]),
    dict(op="rip", box=(45.8, 25.5, 47.9, 26.1), nets=["GND"], layers=[B]),     # a GND stub run across it too
    # U12 (right sensor supply switch) 1.6 mm north: its GND pin clears the L3 bus there and gets a via
    dict(op="rip_ref", ref="U12"),
    dict(op="move", ref="U12", x=57.65, y=27.15, rot=180, side="B"),
    dict(op="rip", box=(58.4, 27.4, 59.8, 28.9), nets=["GND"], layers=[B]),        # its old GND stub
    dict(op="rip", box=(55.2, 28.5, 58.0, 30.0), nets=["/sensors/R_VS"], layers=[B]),     # C49's old tie
    dict(op="rip", box=(49.6, 26.75, 56.0, 26.95), nets=["/sensors/R_VSRC"], layers=[B]),  # to U12's old pin 5
    dict(op="rip_ref", ref="C49"),
    dict(op="move", ref="C49", x=58.55, y=24.75, rot=90, side="B"),
]
EDITS += [dict(op="drop", pad=("U12", "2"), net="GND", margin=2.0, w=0.25, via=0.4, drill=0.2)]
EDITS += [dict(e, margin=6.0, w=0.127, max_ratio=2.5) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "17_input_drc.json", only=("/sensors/R_VSRC",))]
EDITS += [dict(e, margin=8.0, w=0.127, max_ratio=(1.6 if e["net"] == "R_SOC" else 2.5), **({"avoid": [[B, 59.36, 28.35, 60.3, 29.7]]} if e["net"] == "/sensors/R_VS" else {})) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "17_input_drc.json", only=("W_NTC", "W_INLA_M", "R_MTEMP", "/sensors/R_TEMPJ", "R_SOC", "W_EN", "/mcu/LED_A", "/sensors/R_VS", "L_MTEMP"))]
EDITS += [dict(op="drop", pad=p, net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2) for p in (("C46", "2"),)]
EDITS += [dict(op="route", net="/sensors/R_VSRC", a=("pad", "U12", "5"), b=("pad", "C48", "1"), w=0.15, margin=3.0, max_ratio=2.5),
          dict(op="route", net="/sensors/R_VSRC", a=("pad", "U12", "4"), b=("pad", "U12", "5"), w=0.15, margin=1.5)]
EDITS += [dict(op="route", net="/sensors/R_VS", a=("pad", "C49", "1"), b=("pad", "U12", "1"), w=0.15, margin=3.0, max_ratio=2.5),
          dict(op="drop", pad=("C49", "2"), net="GND", margin=2.5, w=0.25, via=0.4, drill=0.2)]
