"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

# single-blocker opens (why probes): lift the blocking run, route the open, re-join the lifted run after it
RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
    dict(op="rip", box=(20.0, 23.0, 20.3, 24.5), nets=["/mcu/MB_RX"], layers=[B], reroute=RR),
    dict(op="rip", box=(43.7, 28.0, 45.2, 31.8), nets=["W_SOC"], layers=[B], reroute=RR),
    dict(op="rip", box=(25.7, 25.9, 26.5, 31.9), nets=["L_INHC"], layers=[L3], reroute=dict(margin=9.0, max_ratio=5.0)),
]
EDITS += [dict(e, margin=6.0, max_ratio=2.5, w=(0.2 if e["net"] in ("+3V3", "+5V") else 0.127))
          for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "18_input_drc.json", only=("+3V3", "L_nFAULT", "L_INHA", "/sensors/L_VSRC", "L_S2", "/sensors/R_H2"))]
