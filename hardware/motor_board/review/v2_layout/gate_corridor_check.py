"""Geometry check of the proposed HS-gate lanes against the placed pads (geom_place.json).
Cells B and A shifted +SH mm in x (proposal).  Copper only (pads, vias, traces); pours not modelled."""
import json, math, sys
from shapely.geometry import box, LineString, Point
SH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
G = json.load(open("/home/smance/projects/thumbsup/.claude/worktrees/layout-v2/hardware/motor_board/kicad/v2/out/geom_place.json"))
CELLB = {"Q3", "Q4", "RS2", "C26", "NT2", "JW2", "TH1"}
CELLA = {"Q1", "Q2", "RS1", "C25", "NT1"}
pads = []
for p in G["pads"]:
    if p["side"] != "T" or not p["num"]:
        continue
    b = p["box"]
    dx = SH if (p["ref"] in CELLB or p["ref"] in CELLA) else 0.0
    pads.append((p["ref"], p["num"], p["net"].split("/")[-1], box(b[0] + dx, b[1], b[2] + dx, b[3])))


def near(geom, net, lim=0.6):
    out = []
    for r, n, pn, g in pads:
        if pn == net:
            continue
        d = geom.distance(g)
        if d < lim:
            out.append((round(d, 3), r, n, pn))
    return sorted(out)[:4]


VIA = 0.3
TW = 0.125


def via(x, y):
    return Point(x, y).buffer(VIA, 16)


def tr(pts):
    return LineString(pts).buffer(TW, 8)


X = SH
items = {
    "C mouth via SH (51.60,6.45) W_C": (via(51.60, 6.45), "W_C"),
    "C mouth via GH (51.60,7.55)": (via(51.60, 7.55), "W_GHC"),
    "C GH stub pin4->via": (tr([(52.80, 7.0), (52.2, 7.55), (51.6, 7.55)]), "W_GHC"),
    "C up-via SH (52.40,17.95)": (via(52.40, 17.95), "W_C"),
    "C up-via GH (53.30,18.55)": (via(53.30, 18.55), "W_GHC"),
    "B mouth via SH (64.50+s,6.45) W_B": (via(64.10 + X, 6.45), "W_B"),
    "B mouth via GH (64.50+s,7.55)": (via(64.10 + X, 7.55), "W_GHB"),
    "B GH stub pin4->via": (tr([(65.29 + X, 7.0), (64.6 + X, 7.55), (64.1 + X, 7.55)]), "W_GHB"),
    "B up-via SH (58.05,6.45) W_B": (via(58.05, 6.45), "W_B"),
    "B up-via GH (58.05,7.55)": (via(58.05, 7.55), "W_GHB"),
    "B L1 GH channel+door": (tr([(58.05, 7.55), (58.05, 12.0), (56.75, 13.4), (56.75, 18.3)]), "W_GHB"),
    "B L1 SH channel+door": (tr([(58.05, 6.45), (58.65, 7.0), (58.65, 12.1), (57.25, 13.6), (57.25, 18.3)]), "W_B"),
    "A mouth via SH (77.00+s,6.45) W_A": (via(76.60 + X, 6.45), "W_A"),
    "A mouth via GH (77.00+s,7.55)": (via(76.60 + X, 7.55), "W_GHA"),
    "A GH stub pin4->via": (tr([(78.2 + X, 7.0), (77.2 + X, 7.55), (76.6 + X, 7.55)]), "W_GHA"),
    "A up-via SH (77.95+s,17.95)": (via(77.40 + X, 17.95), "W_A"),
    "A up-via GH (78.85+s,18.55)": (via(78.30 + X, 18.55), "W_GHA"),
}
print(f"shift of cells B and A: +{SH} mm")
for k, (g, net) in items.items():
    print(f"{k:38s} nearest other-net pads: {near(g, net)}")
P = {(r, n): g for r, n, _, g in pads}


def gap(a, b):
    return round(P[a].distance(P[b]), 3)


print("\nDOORS / CHANNELS (pad-to-pad copper gap, mm):")
print(" C interior: Q5 tab - RS3 GND pad (pinch)   ", gap(("Q5", "5"), ("RS3", "2")))
print(" C: RS3 GND pad - C31 GND pad (L1 GND link) ", gap(("RS3", "2"), ("C31", "2")))
print(" C interior channel: Q6 tab - Q5 tab        ", gap(("Q6", "5"), ("Q5", "5")))
print(" C|B FET row: Q5 tab - Q4 tab               ", gap(("Q5", "5"), ("Q4", "5")))
print(" C|B door: Q5 tab - RS2 SL pad              ", gap(("Q5", "5"), ("RS2", "1")))
print(" C|B shunt row: C31 VBAT pad - RS2 SL pad   ", gap(("C31", "1"), ("RS2", "1")))
print(" B interior channel: Q4 tab - Q3 tab        ", gap(("Q4", "5"), ("Q3", "5")))
print(" RS3 pad gap                                ", gap(("RS3", "1"), ("RS3", "2")))
u2 = P[("U2", "20")]
print(" band rear copper (17.35) -> U2 pin 20 pad   ", round(u2.bounds[1] - 17.35, 3))
for a, b in (((51.6, 6.45), (51.6, 7.55)), ((52.40, 17.95), (53.30, 18.55))):
    d = math.dist(a, b)
    print(f" via pair spacing {d:.2f} -> L2/L3 antipad web (0.7 mm antipads) {d - 0.7:.2f} mm")
