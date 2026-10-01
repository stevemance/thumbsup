"""r2 stage: closing pass on top of r2_main - every remaining signal / rail open with a wide search window, rails necked
to 0.15 mm / 0.4 mm vias where needed, explicit help where the router alone does not find a way (below)."""
import json
import os
from pathlib import Path

import v2_pre
from v2_pre import EDITS, F1, L3, L4, P, route, tr, via, PV, POFV, RV, n_  # noqa: F401
import r2_auto as A

v2_pre.VIA_PITCH = 0.9
v2_pre.STACK_PEN = 4.0
BASE = os.environ.get("R2_BASE", "r2_main")
d = json.load(open(Path(__file__).resolve().parent / "out" / "exp" / BASE / "drc.json"))
nets = sorted({A.re.search(r"\[([^\]]+)\]", u["items"][0]["description"]).group(1).split("/")[-1]
               for u in d["unconnected_items"]} - {"GND"})
POUR = {"VBAT", "BAT_IN", "PSW_S", "VBAT_SW", "W_A", "W_B", "W_C", "W_SLA", "W_SLB", "W_SLC", "L_A", "L_B", "L_C",
        "R_A", "R_B", "R_C", "L_VM", "R_VM"}
nets = [n for n in nets if n not in POUR]
RAILS = [n for n in nets if n in ("+3V3", "+5V", "+3V3A")]
SIG = [n for n in nets if n not in RAILS]
A.route_opens(BASE, SIG, margin=12.0, soft=True)
A.route_opens(BASE, RAILS, margin=12.0, w=0.15, via=0.4, drill=0.2)
A.route_opens(BASE, SIG, margin=20.0, retry=True, soft=True, layer_cost={L3: 2.0})
A.route_opens(BASE, RAILS, margin=20.0, w=0.15, via=0.4, drill=0.2, retry=True, layer_cost={L3: 2.0})
