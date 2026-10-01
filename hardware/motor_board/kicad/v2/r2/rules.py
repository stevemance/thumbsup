"""(r2 copy of gen/out/pr/rules.py: geometry from kicad/gen/out/exp/<exp>/geom_r2.json; via pitch rule)
python3 rules.py BASE_EXP EXP : layer-rule check of the copper EXP added on top of BASE_EXP (geometry exports
out/pr/<exp>_geom.json): band / island / field keep-outs, analog layers and shadows, stacked L3/L4 digital runs,
new vias closer than 1.3 mm to another via."""
import json, math, sys
from pathlib import Path
G = Path(__file__).resolve().parents[2] / "gen"
sys.path.insert(0, str(G))
gb = json.load(open(G / "out" / "exp" / sys.argv[1] / "geom_r2.json")); ga = json.load(open(G / "out" / "exp" / sys.argv[2] / "geom_r2.json"))
import v2_pre as V
sh = lambda n: n.split("/")[-1]
key = lambda t: (t["net"], t["layer"], tuple(t["a"]), tuple(t["b"]))
old = {key(t) for t in gb["tracks"]}
new = [t for t in ga["tracks"] if key(t) not in old]
oldv = {(v["net"], tuple(v["c"])) for v in gb["vias"]}
newv = [v for v in ga["vias"] if (v["net"], tuple(v["c"])) not in oldv]
AN = set(V.ANALOG)
L3, L4 = "In2.Cu", "B.Cu"


def inb(p, b):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def seg_in_box(t, b, n=20):
    return any(inb((t["a"][0] + (t["b"][0] - t["a"][0]) * k / n, t["a"][1] + (t["b"][1] - t["a"][1]) * k / n), b) for k in range(n + 1))


def sd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def overlap_len(t, u, d):
    """length of t lying within d of segment u"""
    n = max(2, int(math.dist(t["a"], t["b"]) / 0.05))
    L = math.dist(t["a"], t["b"]) / n
    return sum(L for k in range(n) if sd(((t["a"][0] * (n - k - .5) + t["b"][0] * (k + .5)) / n, (t["a"][1] * (n - k - .5) + t["b"][1] * (k + .5)) / n), u["a"], u["b"]) < d)


bad = []
an4 = {}
for t in new:
    if t["layer"] == "In1.Cu":
        bad.append(f"L2 track {sh(t['net'])}")
    if t["layer"] in (L3, L4):
        for b in V.BAND:
            if seg_in_box(t, (b[0], b[1], b[2], b[3] - 0.0)) and not seg_in_box(t, (b[0], b[3] - 0.001, b[2], b[3])):
                bad.append(f"band {sh(t['net'])} {t['layer']} {t['a']}->{t['b']}")
                break
    if t["layer"] == L3:
        for u in ("U3", "U4"):
            if seg_in_box(t, V.grow(V.EP[u], 1.5)):
                bad.append(f"L3 in {u} island {sh(t['net'])} {t['a']}->{t['b']}")
    if t["layer"] == L4:
        for u in ("U2", "U3", "U4"):
            if seg_in_box(t, V.grow(V.EP[u], 0.5)):
                bad.append(f"L4 in {u} field {sh(t['net'])} {t['a']}->{t['b']}")
        if t["net"] in AN:
            an4[sh(t["net"])] = an4.get(sh(t["net"]), 0) + math.dist(t["a"], t["b"])
# shadows / stacking between L3 and L4
t3 = [t for t in ga["tracks"] if t["layer"] == L3]
t4 = [t for t in ga["tracks"] if t["layer"] == L4]
newk = {key(t) for t in new}
seen = set()
for a in t3:
    for b in t4:
        if a["net"] == b["net"] or (key(a) not in newk and key(b) not in newk):
            continue
        d = (a["w"] + b["w"]) / 2 + 0.05
        if max(a["a"][0], a["b"][0]) + d < min(b["a"][0], b["b"][0]) or max(b["a"][0], b["b"][0]) + d < min(a["a"][0], a["b"][0]):
            continue
        if max(a["a"][1], a["b"][1]) + d < min(b["a"][1], b["b"][1]) or max(b["a"][1], b["b"][1]) + d < min(a["a"][1], a["b"][1]):
            continue
        L = overlap_len(a, b, d)
        if L <= 0:
            continue
        an = a["net"] in AN or b["net"] in AN
        if an or L > 1.0:
            k = (sh(a["net"]), sh(b["net"]))
            seen.add((("ANALOG-shadow" if an else "stacked"), k, round(L, 2), tuple(round(c, 1) for c in a["a"])))
for s in sorted(seen):
    bad.append(f"{s[0]} L3 {s[1][0]} / L4 {s[1][1]}: {s[2]} mm near {s[3]}")
print(f"{len(new)} new track segments, {len(newv)} new vias")
l3 = {}
for t in new:
    if t["layer"] == L3:
        l3[sh(t["net"])] = l3.get(sh(t["net"]), 0) + math.dist(t["a"], t["b"])
print("new L3 per net (mm):", " ".join(f"{k}:{v:.1f}" for k, v in sorted(l3.items(), key=lambda kv: -kv[1])))
print("analog on L4 per net (mm, bottom-pad hops):", " ".join(f"{k}:{v:.1f}" for k, v in sorted(an4.items(), key=lambda kv: -kv[1])))
for x in bad:
    print("  RULE", x)
pitch = []
for v in newv:
    if sh(v["net"]) == "GND":
        continue
    for w in ga["vias"]:
        if w is v or sh(w["net"]) == "GND":
            continue
        dd = math.dist(v["c"], w["c"])
        if dd < 0.9 and (id(w) > id(v) or (w["net"], tuple(w["c"])) in oldv):
            pitch.append(f"{sh(v['net'])}{tuple(v['c'])} - {sh(w['net'])}{tuple(w['c'])}: {dd:.2f}")
print(f"PITCH new non-GND via pairs < 0.9 mm: {len(pitch)}")
for c in pitch:
    print("   ", c)
close = []
for v in newv:
    for w in ga["vias"]:
        if w is v:
            continue
        dd = math.dist(v["c"], w["c"])
        if dd < 1.3 and (id(w) > id(v) or (w["net"], tuple(w["c"])) in oldv):
            close.append(f"{sh(v['net'])}{tuple(v['c'])} - {sh(w['net'])}{tuple(w['c'])}: {dd:.2f}")
print(f"new vias closer than 1.3 mm to another via (info): {len(close)}")
