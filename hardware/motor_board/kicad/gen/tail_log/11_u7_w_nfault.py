"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
    # the +3V3 run from C17 west under U7's pins to R42 / R50 walled U7's signal pins in: lifted, R42 / R50 dropped to the
    # L4 +3V3 fill and R50 re-tied to D8
    dict(op="rip", box=(21.9, 12.3, 24.1, 15.3), nets=["+3V3"], layers=["B.Cu"]),
]
EDITS += [dict(op="drop", pad=p, net="+3V3", margin=1.8, w=0.2, via=0.4, drill=0.2)
          for p in (("R42", "2"), ("R50", "2"))]
# north-west nets onto the freed L3 corner: L3 preferred, cheap vias
_L3PREF = dict(layer_cost={"B.Cu": 2.0, "F.Cu": 3.0, L3: 1.0, L4: 2.0}, via_cost=0.3)
EDITS += [dict(e, margin=8.0, **_L3PREF) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "11_input_drc.json", only=("W_nFAULT", "R_MTEMP", "/mcu/NRST"))]
EDITS += [dict(op="route", net="+3V3", a=("pad", "R50", "2"), b=("pad", "D8", "2"), w=0.2, margin=3.0, **_L3PREF)]
