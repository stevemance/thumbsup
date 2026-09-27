"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""
import json
from pathlib import Path

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

LN = {"F.Cu": "F.Cu", "B.Cu": "B.Cu", "L3.PWR+SIG": L3, "L4.SIG": L4}
EDITS = []
# segments grow.py lifted (they crossed the cut at a step or tied to a part on the other side): re-route end to end
for r in json.load(open(Path(__file__).resolve().parent / "tail_log" / "14_grow_reroute.json")):
    EDITS.append(dict(op="route", net=r["net"], a=("pt", r["a"][0], r["a"][1], LN[r["layer"]]),
                      b=("pt", r["b"][0], r["b"][1], LN[r["layer"]]), w=max(r["w"], 0.127), margin=8.0, max_ratio=2.5,
                      **({"avoid": [[L3, 45.5, 26.35, 46.4, 27.15]]} if r["net"] == "W_SOC" else {})))
