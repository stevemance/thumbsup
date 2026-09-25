"""Measure the placed board (motor_board.kicad_pcb).  Board-local mm: x right, y toward the rear (front edge y=0).
Run with /usr/bin/python3.

    measure.py gaps [N]            smallest N part-to-part gaps: courtyard gap, copper (pad edge) gap; plus edge distances
    measure.py near REF [R]        every part within R mm (default 3) of REF's courtyard, same side and opposite side
    measure.py dist A.PAD B.PAD    centre distance and pad-edge gap between two pads (e.g. dist C24.1 U2.6)
    measure.py net NAME            every pad on a net with position; the farthest pair
    measure.py part REF            side, position, rotation, courtyard, every pad with net and position
    measure.py loop PHASE          commutation-loop geometry of one bridge cell (A, B or C)
"""
import math
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
OX, OY = 100.0, 70.0
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
bb = b.GetBoardEdgesBoundingBox()
EW = 0.1   # Edge.Cuts line width: the bbox includes half of it on each side
BW, BH = t(bb.GetWidth()) - EW, t(bb.GetHeight()) - EW
OX, OY = t(bb.GetLeft()) + EW / 2, t(bb.GetTop()) + EW / 2


def side(fp):
    return "bottom" if fp.IsFlipped() else "top"


def court(fp):
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer:
            r = g.GetBoundingBox(); xs += [t(r.GetLeft()), t(r.GetRight())]; ys += [t(r.GetTop()), t(r.GetBottom())]
    if not xs:
        for p in fp.Pads():
            r = p.GetBoundingBox(); xs += [t(r.GetLeft()), t(r.GetRight())]; ys += [t(r.GetTop()), t(r.GetBottom())]
    return min(xs) - OX, min(ys) - OY, max(xs) - OX, max(ys) - OY


def pads(fp):
    out = []
    for p in fp.Pads():
        r = p.GetBoundingBox()
        out.append(dict(num=p.GetNumber(), net=p.GetNetname().split("/")[-1], x=t(p.GetPosition().x) - OX, y=t(p.GetPosition().y) - OY,
                        box=(t(r.GetLeft()) - OX, t(r.GetTop()) - OY, t(r.GetRight()) - OX, t(r.GetBottom()) - OY),
                        tht=p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH),
                        layers=("both" if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else side(fp))))
    return out


def box_gap(a, c):
    dx = max(c[0] - a[2], a[0] - c[2], 0.0)
    dy = max(c[1] - a[3], a[1] - c[3], 0.0)
    if dx == 0 and dy == 0:
        return -min(a[2] - c[0], c[2] - a[0], a[3] - c[1], c[3] - a[1])   # overlap depth (negative)
    return math.hypot(dx, dy)


def pad_gap(pa, pb):
    """edge-to-edge gap of two pads using their shapes."""
    sa, sb = pa.GetEffectiveShape(), pb.GetEffectiveShape()
    d = sa.Collide(sb, pcbnew.FromMM(20)) if False else None
    return None


def cmd_gaps(n=40):
    refs = list(fps)
    rows = []
    P = {r: pads(fps[r]) for r in refs}
    C = {r: court(fps[r]) for r in refs}
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            fa, fc = fps[a], fps[c]
            same = side(fa) == side(fc)
            tha = any(p["tht"] for p in P[a]); thc = any(p["tht"] for p in P[c])
            if not same and not (tha or thc):
                continue
            g = box_gap(C[a], C[c]) if same else None
            cu = None
            for pa in P[a]:
                for pc in P[c]:
                    if pa["layers"] != "both" and pc["layers"] != "both" and pa["layers"] != pc["layers"]:
                        continue
                    d = box_gap(pa["box"], pc["box"])
                    cu = d if cu is None or d < cu else cu
            if cu is None and g is None:
                continue
            rows.append((min(x for x in (g, cu) if x is not None), a, c, g, cu, "same side" if same else "through-hole vs other side"))
    rows.sort()
    print(f"board {BW:.2f} x {BH:.2f} mm")
    print("smallest gaps (courtyard gap / pad-box gap, mm):")
    for _, a, c, g, cu, what in rows[:n]:
        print(f"  {a:6s} {c:6s} courtyard {'' if g is None else f'{g:6.2f}'}  pads {'' if cu is None else f'{cu:6.2f}'}  ({what})")
    print("closest to the board edge (courtyard / nearest pad edge, mm):")
    er = []
    for r in refs:
        cx0, cy0, cx1, cy1 = C[r]
        ce = min(cx0, cy0, BW - cx1, BH - cy1)
        pe = min(min(p["box"][0], p["box"][1], BW - p["box"][2], BH - p["box"][3]) for p in P[r])
        er.append((ce, r, pe))
    for ce, r, pe in sorted(er)[:n]:
        print(f"  {r:6s} courtyard {ce:6.2f}  pad {pe:6.2f}  ({side(fps[r])})")


def cmd_near(ref, rad=3.0):
    a = court(fps[ref])
    print(f"{ref} ({side(fps[ref])}) courtyard {tuple(round(v, 2) for v in a)}")
    for r, fp in sorted(fps.items()):
        if r == ref:
            continue
        g = box_gap(a, court(fp))
        if g <= rad:
            print(f"  {r:6s} {side(fp):6s} courtyard gap {g:6.2f}")


def find_pad(spec):
    ref, num = spec.split(".", 1)
    for p in pads(fps[ref]):
        if p["num"] == num:
            return p
    raise SystemExit(f"no pad {spec}")


def cmd_dist(a, c):
    pa, pc = find_pad(a), find_pad(c)
    print(f"{a} ({pa['net']}) at ({pa['x']:.2f},{pa['y']:.2f}) [{pa['layers']}]  {c} ({pc['net']}) at ({pc['x']:.2f},{pc['y']:.2f}) [{pc['layers']}]")
    print(f"  centre distance {math.hypot(pa['x'] - pc['x'], pa['y'] - pc['y']):.2f} mm, pad-edge gap {box_gap(pa['box'], pc['box']):.2f} mm")


def cmd_net(name):
    pts = []
    for r, fp in fps.items():
        for p in pads(fp):
            if p["net"] == name:
                pts.append((r, p))
    for r, p in sorted(pts, key=lambda q: (q[0], q[1]["num"])):
        print(f"  {r}.{p['num']:4s} ({p['x']:6.2f},{p['y']:6.2f}) {p['layers']}")
    far = max(((math.hypot(p['x'] - q['x'], p['y'] - q['y']), f"{r}.{p['num']}", f"{s}.{q['num']}") for r, p in pts for s, q in pts), default=None)
    if far:
        print(f"  farthest pair {far[1]} - {far[2]}: {far[0]:.2f} mm")


def cmd_part(ref):
    fp = fps[ref]
    pos = fp.GetPosition()
    print(f"{ref} {fp.GetValue()} {side(fp)} at ({t(pos.x) - OX:.2f},{t(pos.y) - OY:.2f}) rot {fp.GetOrientationDegrees():.0f} "
          f"courtyard {tuple(round(v, 2) for v in court(fp))}")
    for p in pads(fp):
        print(f"  {p['num']:4s} {p['net']:14s} ({p['x']:6.2f},{p['y']:6.2f}) {p['layers']}")


CELLS = {"A": ("Q1", "Q2", "RS1", "C25", "JW1"), "B": ("Q3", "Q4", "RS2", "C26", "JW2"), "C": ("Q5", "Q6", "RS3", "C31", "JW3")}


def cmd_loop(ph):
    hs, ls, rs, cap, jw = CELLS[ph]
    cp = {p["net"]: p for p in pads(fps[cap])}
    hs_tab = [p for p in pads(fps[hs]) if p["num"] == "5"][0]
    hs_src = [p for p in pads(fps[hs]) if p["num"] in ("1", "2", "3")]
    ls_tab = [p for p in pads(fps[ls]) if p["num"] == "5"][0]
    ls_src = [p for p in pads(fps[ls]) if p["num"] in ("1", "2", "3")]
    rsp = {p["num"]: p for p in pads(fps[rs])}
    seq = [("cap VBAT", cp["VBAT"]), ("HS drain tab", hs_tab), ("HS source pins", {"x": sum(p["x"] for p in hs_src) / 3, "y": sum(p["y"] for p in hs_src) / 3}),
           ("LS drain tab", ls_tab), ("LS source pins", {"x": sum(p["x"] for p in ls_src) / 3, "y": sum(p["y"] for p in ls_src) / 3}),
           ("shunt pad 1", rsp["1"]), ("shunt pad 2 (GND)", rsp["2"]), ("cap GND", cp["GND"])]
    L, area = 0.0, 0.0
    for i, (n, p) in enumerate(seq):
        q = seq[(i + 1) % len(seq)][1]
        L += math.hypot(p["x"] - q["x"], p["y"] - q["y"])
        area += p["x"] * q["y"] - q["x"] * p["y"]
        print(f"  {n:18s} ({p['x']:6.2f},{p['y']:6.2f})")
    print(f"phase {ph}: loop path through the pad centres {L:.1f} mm, enclosed area {abs(area) / 2:.1f} mm2 "
          f"(polygon of pad centres; the real current path follows the copper)")
    print(f"  cap GND to shunt GND pad-edge gap {box_gap(cp['GND']['box'], rsp['2']['box']):.2f} mm; "
          f"cap VBAT to HS tab pad-edge gap {box_gap(cp['VBAT']['box'], hs_tab['box']):.2f} mm")


def cmd_orient():
    """0805/1206/2512 parts: which way their length runs and how far they are from the nearest mounting hole
    (DESIGN 6.10: parallel to the nearest board edge / standoff line, >= 3 mm from the holes)."""
    mh = {r: (t(f.GetPosition().x) - OX, t(f.GetPosition().y) - OY) for r, f in fps.items() if r.startswith("MH")}
    print("mounting holes:", {k: (round(x, 2), round(y, 2)) for k, (x, y) in mh.items()})
    for r, f in sorted(fps.items()):
        name = f.GetFPIDAsString()
        if not any(k in name for k in ("0805", "1206", "2512")):
            continue
        x, y = t(f.GetPosition().x) - OX, t(f.GetPosition().y) - OY
        cx0, cy0, cx1, cy1 = court(f)
        d = min(box_gap((cx0, cy0, cx1, cy1), (a - 1.1, c - 1.1, a + 1.1, c + 1.1)) for a, c in mh.values())
        along = "x" if round(f.GetOrientationDegrees()) % 180 == 0 else "y"
        edge = min((y, "front"), (BH - y, "rear"), (x, "left"), (BW - x, "right"))
        ok = (along == "x") == (edge[1] in ("front", "rear"))
        nets = sorted({p.GetNetname().split("/")[-1] for p in f.Pads()})
        print(f"  {r:5s} {name.split(':')[1][:20]:20s} {side(f):6s} ({x:5.1f},{y:5.1f}) length along {along}; nearest edge {edge[1]} "
              f"{edge[0]:4.1f} mm -> {'parallel' if ok else 'PERPENDICULAR'}; courtyard to nearest hole {d:4.1f} mm; nets {'/'.join(nets)}")


GATES = [("A", "Q1", "8", "9", "Q2", "10", "11"), ("B", "Q3", "17", "16", "Q4", "15", "14"), ("C", "Q5", "18", "19", "Q6", "20", "21")]


def cmd_gates():
    """gate-drive loop lengths, pin to pin (Manhattan, pad centres): U2 GHx->HS gate, SHx->HS source,
    GLx->LS gate, SLx->LS source (DRV8323 p75: short, low side most critical)."""
    u = {p["num"]: p for p in pads(fps["U2"])}
    for ph, hs, gh, sh, ls, gl, sl in GATES:
        H = {p["num"]: p for p in pads(fps[hs])}
        L = {p["num"]: p for p in pads(fps[ls])}
        man = lambda a, b: abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
        hsrc = min((H[n] for n in ("1", "2", "3")), key=lambda q: man(u[sh], q))
        lsrc = min((L[n] for n in ("1", "2", "3")), key=lambda q: man(u[sl], q))
        print(f"  phase {ph}: GH{ph}->{hs}.4 {man(u[gh], H['4']):5.1f} mm, SH{ph}->{hs} source {man(u[sh], hsrc):5.1f} mm, "
              f"GL{ph}->{ls}.4 {man(u[gl], L['4']):5.1f} mm, SL{ph}->{ls} source {man(u[sl], lsrc):5.1f} mm")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    {"gaps": lambda: cmd_gaps(int(a[1]) if len(a) > 1 else 40), "near": lambda: cmd_near(a[1], float(a[2]) if len(a) > 2 else 3.0),
     "dist": lambda: cmd_dist(a[1], a[2]), "net": lambda: cmd_net(a[1]), "part": lambda: cmd_part(a[1]),
     "loop": lambda: cmd_loop(a[1]), "orient": cmd_orient, "gates": cmd_gates}[a[0]]()
