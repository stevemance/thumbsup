"""Routing blocks, in order.  Each request: net, a, b (endpoints: ("pad", ref, num) | ("via", x, y) | ("pt", x, y, layer)),
layers, layer_cost, via_cost, margin (search window around the endpoints, mm), optional w/clr overrides, tag.
A request with "fixed" = {"tracks": [...], "vias": [...]} passes hand-planned geometry straight through.
Coordinates: board-local mm (front-left corner, y toward the rear)."""
import json
import os
import sys

F, L3, L4, B = "F.Cu", "In2.Cu", "In3.Cu", "B.Cu"      # L2 (In1) and L5 (In4) are GND planes
DEFINED = []                    # request tags of the blocks defined so far, in order


class Blocks(dict):
    def __setitem__(self, k, reqs):
        super().__setitem__(k, reqs)
        DEFINED.extend(r.get("tag") or r.get("net") for r in reqs)


BLOCKS = Blocks()
_SPACE = None
_ADDED = set()


def space():
    """Clearance model for picking hand-placed spots: the base board plus the copper that the blocks defined so far
    laid down in the last build (out/route/routes.json; earlier blocks only, so picks stay stable build to build)."""
    global _SPACE
    here = __import__("pathlib").Path(__file__).resolve().parent
    if _SPACE is None:
        sys.path.insert(0, str(here))
        from geo import Space
        _SPACE = Space(json.load(open(here / "out" / "route" / "geom.json")))
    rp = here / "out" / "route" / "routes.json"
    if rp.exists():
        want = set(DEFINED) - _ADDED
        for r in json.load(open(rp)):
            if r.get("ok") and r["tag"] in want:
                for t in r["tracks"]:
                    _SPACE.add_track(t["pts"], t["w"], t["layer"], t["net"])
                for v in r["vias"]:
                    _SPACE.add_via(v["c"], v["d"], v["drill"], v["net"])
        _ADDED.update(want)
    return _SPACE


def pick_via(net, target, d=0.4, drill=0.2, rmax=1.5, step=0.05):
    """Nearest legal via spot to `target` (spiral over a grid), claimed in the model so later picks respect it."""
    sp = space()
    cands = sorted(((i * step, j * step) for i in range(-int(rmax / step), int(rmax / step) + 1)
                    for j in range(-int(rmax / step), int(rmax / step) + 1)), key=lambda o: o[0] ** 2 + o[1] ** 2)
    for dx, dy in cands:
        c = (round(target[0] + dx, 3), round(target[1] + dy, 3))
        if sp.via_ok(c, d, drill, net):
            sp.add_via(c, d, drill, net)
            return c
    raise SystemExit(f"no via spot for {net} near {target}")


def via(net, c, d=0.4, drill=0.2):
    return dict(net=net, c=list(c), d=d, drill=drill)


def trk(net, layer, pts, w):
    pts = [list(p) for k, p in enumerate(pts) if k == 0 or tuple(p) != tuple(pts[k - 1])]    # no zero-length segments
    return dict(net=net, layer=layer, pts=pts, w=w)


# ---------------------------------------------------------------- block 1: weapon gate drive + Kelvin sense
# Base-board edits this block relies on (base_edits.py): NT2 flat on RS2's GND pad inner-front corner and NT3 on RS3's
# inner-rear corner (sense pads in the shunt pad gaps); R24 moved between JW3's and JW2's solder zones; GND vias at
# (55.4, 15.9), (45.5, 16.7), (46.7, 16.5) dropped; the L3 VBAT feed trimmed to y 6.0-18.2 over the bridge.
#
# U2's front row (rot 180, pads y 19.125-20.0, pin 13 at x 56.25, 0.5 pitch leftward) runs the opposite way round to
# each cell's gate vias, so the escape is planned by hand here and checked by DRC; the router only does open ground.
#   fan-out: pins 13-22 drop on short top stubs into two staggered rows of 0.4/0.2 vias (y 18.77 / 18.10).
#   phase B (bottom): GHB and SHB go west just in front of the rows, front down the channel under RS2's GND pad (left
#     of its pad vias), then east: GHB into the HS gate via, SHB along y 7.0 to the far (quiet) end of Q3's source pins.
#     GLB goes straight front, right of RS2's pad vias, and west into the LS gate via between the VBAT column's vias.
#   phase B Kelvin (L3): SN from a via in NT2's sense pad, SL from a via in the shunt pad gap; a pair in front of the
#     rows through the rear edge of the L3 VBAT feed, to pins 13/14.
#   phase C: SNC/SLC/GLC/SHC up behind the rows on L3 (clear under U2), west, down a via staircase left of U2 to the
#     bottom; GHC behind the rows on the bottom.  Bottom columns x 47.5-49.75, left to right SN, SL, GL, SH, GH, which
#     is the order the targets take front to back, so the router's columns never cross.
#   phase A: from U2's right side; router.
# SH (gate return) vias sit at the far end of each HS FET's source-pin row, away from where the phase current leaves
# (a quiet Kelvin point); the phase dividers' top resistors get their own phase vias.
# The divided phase voltages and the FET NTC (W_VA, W_VB, W_NTC) must cross every gate bundle to reach the MCU: they
# drop to an L3 lane strip along the front (y 4.9-5.8, between the phase-wire pads and the trimmed VBAT feed).  Their
# escape vias are placed here; the lanes are routed with the long signals.
CELLS = {"A": 60.5, "B": 48.0, "C": 35.5}
PIN_X = {n: 56.25 - 0.5 * (n - 13) for n in range(13, 25)}
R1, R2 = 18.77, 18.10
ROW = {13: R1, 15: R1, 17: R1, 19: R1, 21: R1, 14: R2, 16: R2, 18: R2, 20: R2, 22: R2}
NETPIN = {13: "/weapon/W_SNB", 14: "/weapon/W_SLB", 15: "/weapon/W_GLB", 16: "/weapon/W_B", 17: "/weapon/W_GHB",
          18: "/weapon/W_GHC", 19: "/weapon/W_C", 20: "/weapon/W_GLC", 21: "/weapon/W_SLC", 22: "/weapon/W_SNC"}
SH = {"A": (67.5, 7.4), "B": (59.85, 6.5), "C": (47.35, 6.5)}   # quiet spots: B, C at the far end of the HS source-pin
# row; A in the dead-end strip behind Q1's gate pin (so phase A's bundle arrives in order)
GH = {ph: (x0 + 6.54, 6.42) for ph, x0 in CELLS.items()}          # existing gate escape vias (vias_and_pack.py)
GL = {ph: (x0 + 5.95, 11.9) for ph, x0 in CELLS.items()}
SLV = {"A": (63.7, 15.35), "B": (51.2, 16.4), "C": (38.7, 15.35)}  # Kelvin SL vias in the shunt pad gaps
SNV = {"A": (63.6, 13.85), "B": (51.1, 13.85), "C": (38.6, 16.85)}                     # vias in NT1-3's sense pads (filled via-in-pad)


def N(s):
    return "/weapon/W_" + s


T_, V_ = [], []
for pin, y in ROW.items():
    n = NETPIN[pin]
    V_.append(via(n, (PIN_X[pin], y)))
    T_.append(trk(n, F, [(PIN_X[pin], 19.3), (PIN_X[pin], y)], 0.2 if ("_SL" in n or "_SN" in n) else 0.25))
for ph in CELLS:
    V_ += [via(N(ph), SH[ph]), via(N("SL" + ph), SLV[ph])]
for ph, x in (("A", 62.8), ("C", 37.95)):                          # SL from the shunt source pad's inner edge
    T_.append(trk(N("SL" + ph), F, [(x, 15.35), SLV[ph]], 0.2))
T_.append(trk(N("SLB"), F, [(50.45, 16.4), SLV["B"]], 0.2))
V_ += [via(N("SN" + ph), c) for ph, c in SNV.items()]
# phase B Kelvin pair, L3
T_ += [trk(N("SNB"), L3, [SNV["B"], (52.3, 15.05), (52.3, 16.95), (52.55, 17.2), (56.25, 17.2), (56.25, R1)], 0.2),
       trk(N("SLB"), L3, [SLV["B"], (51.2, 17.57), (55.75, 17.57), (55.75, R2)], 0.2)]
# phase B gates, bottom
T_ += [trk(N("GHB"), B, [(54.25, R1), (54.25, 17.8), (54.05, 17.6), (52.65, 17.6), (52.45, 17.4), (52.45, 6.62),
                         (52.65, 6.42), GH["B"]], 0.25),
       trk(N("B"), B, [(54.75, R2), (54.75, 17.4), (54.55, 17.2), (53.1, 17.2), (52.9, 17.0), (52.9, 7.2),
                       (53.1, 7.0), (59.35, 7.0), SH["B"]], 0.2),
       trk(N("GLB"), B, [(55.25, R1), (55.25, 13.75), (55.0, 13.5), (55.0, 12.1), (54.8, 11.9), GL["B"]], 0.25)]
# phase C: L3 behind the rows to the staircase; GHC on the bottom behind the rows
# SNC's stair via sits north of the others, reached by an L3 lane at y 18.1 (just inside the VBAT feed's rear edge,
# like the phase B Kelvin pair), so the top-layer strip in front of U2 pins 23/24 stays free for W_SOB/W_SOC
STAIR = {"SNC": (47.15, 17.65), "SLC": (48.05, 19.05), "GLC": (48.6, 19.72), "C": (49.1, 20.1)}
T_ += [trk(N("SNC"), L3, [(51.75, R2), (51.55, 17.9), (47.4, 17.9), STAIR["SNC"]], 0.15),
       trk(N("SLC"), L3, [(52.25, R1), (52.25, 19.25), (48.25, 19.25), STAIR["SLC"]], 0.2),
       trk(N("GLC"), L3, [(52.75, R2), (52.75, 19.63), (48.69, 19.63), STAIR["GLC"]], 0.2),
       trk(N("C"), L3, [(53.25, R1), (53.25, 20.0), (49.3, 20.0), STAIR["C"]], 0.2),
       trk(N("GHC"), B, [(53.75, R2), (53.75, 19.25), (49.95, 19.25), (49.75, 19.05), (49.75, 18.0)], 0.25)]
V_ += [via(N(n), c) for n, c in STAIR.items()]
# divider phase vias + divided-node escapes to the L3 front strip, NTC escape
T_ += [trk(N("C"), B, [(41.35, 6.75), (41.6, 7.0), (41.6, 7.5)], 0.2),            # R26.1 -> phase C copper
       trk(N("B"), B, [(49.01, 4.5), (49.9, 4.5)], 0.2),                           # R24.1 -> phase B copper
       trk(N("A"), B, [(62.11, 3.0), (62.11, 3.9)], 0.2),                          # R22.1 -> phase A copper
       trk("W_VB", B, [(47.99, 4.5), (47.3, 4.5)], 0.15),
       trk("W_VA", B, [(61.09, 3.0), (59.6, 3.0)], 0.15),
       trk("W_NTC", F, [(58.73, 16.18), (58.73, 17.0)], 0.2),
       trk("W_NTC", B, [(58.73, 17.0), (59.5, 17.0), (60.3, 16.2), (60.3, 5.62)], 0.15)]
V_ += [via(N("C"), (41.35, 6.75)), via(N("B"), (49.9, 4.5)), via(N("A"), (62.11, 3.9)),
       via("W_VB", (47.3, 4.5)), via("W_VA", (59.6, 3.0)), via("W_NTC", (58.73, 17.0)), via("W_NTC", (60.3, 5.62))]
# phase A: pins 8-10 are boxed in by C24's pads, so they drop into a via column between U2 and C24
for pin, y, yv in ((10, 21.25, 21.25), (9, 21.75, 21.85), (8, 22.25, 22.45)):
    n = {10: N("GLA"), 9: N("A"), 8: N("GHA")}[pin]
    bend = (57.4, y) if yv - y > 0.1 else (57.6, y)               # GHA bends early to clear SHA's via
    T_.append(trk(n, F, [(57.2, y), bend, (bend[0] + yv - y, yv), (57.8, yv)], 0.25))
    V_.append(via(n, (57.8, yv)))
b1 = [dict(tag="U2 front escape + bridge vias (fixed)", fixed=dict(tracks=T_, vias=V_))]


def bot(tag, net, a, b, margin=5.0, **kw):
    return dict(tag=tag, net=net, a=a, b=b, layers=[B], via_cost=1.0, margin=margin, **kw)


b1 += [   # phase C bottom columns, rear-most target first so the later ones pass in front
    bot("SLC", N("SLC"), ("via", *STAIR["SLC"]), ("via", *SLV["C"]), w=0.2),   # W_SLx is a Power-class net: Kelvin run 0.2
    bot("SNC", N("SNC"), ("via", *STAIR["SNC"]), ("via", *SNV["C"])),
    bot("GLC", N("GLC"), ("via", *STAIR["GLC"]), ("via", *GL["C"])),
    bot("SHC", N("C"), ("via", *STAIR["C"]), ("via", *SH["C"]), w=0.2),
    bot("GHC", N("GHC"), ("pt", 49.75, 18.0, B), ("via", *GH["C"])),
]
FB = dict(layers=[F, B], layer_cost={F: 1.2, B: 1.0}, via_cost=1.0, margin=6.0)
b1 += [   # phase A from U2's right side
    dict(tag="SNA", net=N("SNA"), a=("pad", "U2", "12"), b=("via", *SNV["A"]), **FB),
    dict(tag="SLA", net=N("SLA"), a=("pad", "U2", "11"), b=("via", *SLV["A"]), w=0.2, **FB),
    bot("GLA", N("GLA"), ("via", 57.8, 21.25), ("via", *GL["A"]), margin=3.0),
    bot("SHA", N("A"), ("via", 57.8, 21.85), ("via", *SH["A"]), w=0.25, margin=3.0),
    bot("GHA", N("GHA"), ("via", 57.8, 22.45), ("via", *GH["A"]), margin=3.0),
]
BLOCKS["1 weapon gate drive + Kelvin"] = b1

# ---------------------------------------------------------------- block 2: U2 local (buck loop, charge pump, straps)
# Buck first (switching loop: VIN cap C27 -> pin 47, SW pin 45 -> D2 / C28 bootstrap / L1, all on top and short),
# then the charge-pump and VM caps, DVDD, the three strap resistors, FB and EN dividers.  Top only where it fits;
# the router may drop to the bottom for the longer divider legs.
TOP = dict(layers=[F, B], layer_cost={F: 1.0, B: 1.6}, via_cost=2.0, margin=3.0)


def pp(tag, net, a, b, **kw):
    q = dict(TOP)
    q.update(kw)
    return dict(tag=tag, net=net, a=("pad", *a.split(".")), b=("pad", *b.split(".")), **q)


# charge pump: pins 5/4/3 fan out as parallel 0.2 lanes (0.5 pitch kept through the 45-degree jog under C24)
CP = [trk("VBAT", F, [(55.75, 26.6), (55.75, 27.0), (56.5, 27.75), (57.5, 27.75)], 0.2),      # VIN: pin 47 -> C27
      trk("/weapon/BUCK_EN", F, [(56.25, 26.6), (56.25, 27.0), (56.5, 27.25), (59.3, 27.25), (59.7, 27.6)], 0.15),  # EN
      trk("VBAT", F, [(60.0, 29.6), (60.0, 30.6), (60.7, 31.3), (61.1, 31.3)], 0.25),     # R4 top -> R402's VBAT pad
      trk("/weapon/BUCK_EN", F, [(60.3, 27.72), (61.4, 27.72)], 0.15),                    # R4 -> C10
      trk("/weapon/BUCK_EN", F, [(59.6, 28.1), (59.12, 28.58), (59.12, 30.6), (58.92, 30.8), (57.6, 30.8),
                                 (57.49, 31.2)], 0.15),                                       # R4 -> R5, down the C27/R4 gap
      trk("/weapon/BUCK_FB", F, [(57.2, 25.75), (57.55, 25.75), (58.19, 26.4)], 0.15),       # FB pin -> R20
      trk("/weapon/BUCK_FB", F, [(58.19, 26.4), (58.19, 26.0), (60.19, 26.0), (60.19, 26.4)], 0.15),  # R20 -> R21, north
      trk("/weapon/BUCK_CB", F, [(54.25, 26.9), (54.25, 27.05), (53.85, 27.45), (53.85, 28.85), (53.65, 29.05),
                                  (52.5, 29.05)], 0.15),       # bootstrap: down west of D2, into C28 below U2's rear escape band
      trk("+3V3", F, [(50.06, 20.835), (48.85, 20.835)], 0.15),     # VREF: straight, between W_SOA and pin 27   # VREF: pin 26 -> C23
      trk("/weapon/U2_VCP", F, [(57.2, 23.75), (57.7, 23.75), (57.95, 24.0), (60.45, 24.0), (60.45, 23.4)], 0.2),
      trk("/weapon/U2_CPH", F, [(57.2, 24.25), (57.7, 24.25), (57.95, 24.5), (60.22, 24.5), (60.22, 25.0)], 0.2),
      trk("/weapon/U2_CPL", F, [(57.2, 24.75), (57.7, 24.75), (57.95, 25.0), (58.5, 25.0)], 0.2)]
b2 = [
    dict(tag="charge pump lanes (fixed)", fixed=dict(tracks=CP, vias=[])),
    pp("SW U2-D2", "/weapon/BUCK_SW", "U2.45", "D2.1", w=0.3, layers=[F]),        # 0.3: leaves a 0.5-pitch pin
    pp("SW D2-L1", "/weapon/BUCK_SW", "D2.1", "L1.1", w=0.6, layers=[F]),
    pp("SW C28", "/weapon/BUCK_SW", "C28.2", "D2.1", w=0.4, layers=[F]),
    pp("VM C24", "VBAT", "C24.1", "U2.6", w=0.4, layers=[F]),
    pp("VM 6-7", "VBAT", "U2.6", "U2.7", w=0.25, layers=[F]),
    pp("VCP cap VM", "VBAT", "C21.2", "C24.1", w=0.3),
    pp("DVDD", "/weapon/U2_DVDD", "C22.1", "U2.36", w=0.25),
    pp("MODE", "/weapon/U2_MODE", "R44.1", "U2.29"),
    pp("IDRIVE", "/weapon/U2_IDRIVE", "R45.1", "U2.30"),
    pp("VDS", "/weapon/U2_VDS", "R46.1", "U2.31"),
]
BLOCKS["2 U2 local"] = b2


# ---------------------------------------------------------------- block 5: U1 fan-out under its own body
# U1 (LQFP-64, bottom) has no exposed pad, so the 9.8 x 9.8 mm inside its pin ring is a free via field.  Each pin
# whose net leaves U1's immediate ring of bottom-side parts gets a straight 0.15 stub inward to a 0.4/0.2 via;
# depths step through 0.45/1.15/1.85/2.55 mm past the pad end so neighbouring vias never touch (at 0.5 pitch a
# neighbour's via can never reach a stub: 0.2 + 0.075 + 0.15 < 0.5).  The vias then carry the pin on L3 (or F).
# Pins whose only partners are bottom-side parts within 3 mm stay on the bottom (hooked up outward later).
def u1_fanout(skip=()):
    here = __import__("pathlib").Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    from geo import Space
    g = json.load(open(here / "out" / "route" / "geom.json"))
    sp = Space(g, clr=0.16)
    u1 = [p for p in g["pads"] if p["ref"] == "U1"]
    bynet = {}
    for p in g["pads"]:
        bynet.setdefault(p["net"], []).append(p)
    tracks, vias, local, fails = [], [], [], []
    # corner pins first (least room), then the rest from the side centres outward
    order = sorted(u1, key=lambda p: -max(abs(p["c"][0] - 35.5), abs(p["c"][1] - 26.0)) - 0.001 * min(
        abs(p["c"][0] - 35.5), abs(p["c"][1] - 26.0)))
    for p in order:
        if p["num"] in skip:
            continue
        x0_, y0_, x1_, y1_ = p["box"]
        cx, cy = p["c"]
        net = p["net"]
        others = [q for q in bynet[net] if q["ref"] != "U1"]
        near_b = [q for q in others if "B.Cu" in q["layers"] and abs(q["c"][0] - cx) + abs(q["c"][1] - cy) < 3.0]
        if net not in ("GND", "+3V3") and others and len(near_b) == len(others):
            local.append(p["num"])
            continue
        if y1_ - y0_ > x1_ - x0_:                                   # vertical pad: top or bottom row
            d = (0.0, 1.0) if cy < 26 else (0.0, -1.0)
            end = (cx, y1_ if cy < 26 else y0_)
        else:
            d = (1.0, 0.0) if cx < 35.5 else (-1.0, 0.0)
            end = (x1_ if cx < 35.5 else x0_, cy)
        side = (-d[1], d[0])                                        # along the row
        w = 0.25 if net in ("GND", "+3V3") else 0.15
        vd, vdr = (0.45, 0.25) if net == "GND" else (0.4, 0.2)
        best = None
        for depth in (0.45, 0.8, 1.15, 1.5, 1.85, 2.2, 2.55, 2.9, 3.25, 3.6):
            for lat in (0.0, 0.25, -0.25, 0.5, -0.5):
                bend = (end[0] + d[0] * max(0.0, depth - 0.35), end[1] + d[1] * max(0.0, depth - 0.35))
                c = (round(bend[0] + d[0] * 0.35 + side[0] * lat, 3), round(bend[1] + d[1] * 0.35 + side[1] * lat, 3))
                pts = [tuple(p["c"]), end] + ([bend] if lat else []) + [c]
                if sp.via_ok(c, vd, vdr, net) and sp.track_ok(pts[1:], w, B, net):
                    best = (c, pts)
                    break
            if best:
                break
        if not best:
            fails.append(p["num"])
            continue
        c, pts = best
        sp.add_via(c, vd, vdr, net)
        sp.add_track(pts[1:], w, B, net)
        vias.append(via(net, c, vd, vdr))
        tracks.append(trk(net, B, pts, w))
    tag = f"U1 fan-out (fixed; bottom-local: {' '.join(sorted(local, key=int))}; no spot: {' '.join(sorted(fails, key=int))})"
    return [dict(tag=tag, fixed=dict(tracks=tracks, vias=vias))]


BLOCKS["5 U1 fan-out"] = u1_fanout(skip=("57", "47"))   # nCS: via placed with the east bus's west end (8b); GND 47: its via sat in nCS's J2 gap (block 4 re-drops it)


# ---------------------------------------------------------------- auto blocks: frozen pair lists (make_pairs.py)
def auto(name, first=(), **kw):
    """Requests from pairs/<name>.json: the listed nets first (in that order), then shortest first."""
    here = __import__("pathlib").Path(__file__).resolve().parent
    pairs = json.load(open(here / "pairs" / f"{name}.json"))
    rank = {n: k for k, n in enumerate(first)}
    pairs.sort(key=lambda p: (rank.get(p["net"], len(rank)), p["dist"]))
    q = dict(layers=[F, B], layer_cost={F: 1.0, B: 1.2}, via_cost=1.5, margin=3.0)
    q.update(kw)
    out = []
    for p in pairs:
        r = dict(tag=f"{p['net']} {p['a'][1]}-{p['b'][1]}", net=p["net"], a=tuple(p["a"]), b=tuple(p["b"]), **q)
        if p["net"] in NARROW and "w" not in r:
            r["w"] = NARROW[p["net"]]
        out.append(r)
    for r in list(out):                       # retry pass for the failures: wider window, cheaper vias, L3 allowed
        out.append(dict(r, retry=True, margin=7.0, via_cost=0.8, layers=[F, L3, L4, B],
                        layer_cost={F: 1.0, B: 1.2, L3: 1.5, L4: 1.2}))
    return out


# logic rails and pack-voltage taps in the auto blocks: fine-pitch pins, < 0.5 A per branch
NARROW = {"+3V3": 0.25, "+5V": 0.3, "VBAT": 0.3}


# block 3: pack entry / power switch / current monitor / ARM / BMS corner (front-left)
BLOCKS["3 power switch corner"] = auto("b3_power_switch", first=(
    "/power/PSW_G", "/power/PSW_S", "/power/BAT_IN", "/power/PSW_CAP", "/power/PSW_EN", "/power/PSW_DV",
    "/power/PSW_RG", "/power/VBAT_SW", "/power/INA_INP", "/power/INA_INN"))


# block 6a: U3 / U4 charge pump + VM caps, hand-planned (caps re-placed to the pin order, see base_edits.PADPOS).
# U3 front row: VM 11-9 (x 20.75-21.75), CP 8 (22.25), CPH 7 (22.75), CPL 6 (23.25), SWBK 5 (23.75), FBBK 3 (24.75).
# VM pins tied by a bar and dropped straight into C303's VM pad; CP straight into C303's CP pad; CPH straight out to
# C304 one row further; CPL out then across under C304's CPL pad; SWBK/FBBK through vias to R300/C307 on the bottom.
# C300/C301 VM pads join C303's.  U4 is the mirror image (x -> 89.5 - x, y -> 54.5 - y).
def drive_caps():
    L = dict(VM="/drive_left/L_VM", CP="/drive_left/L_CP", CPH="/drive_left/L_CPH", CPL="/drive_left/L_CPL",
             SW="/drive_left/L_SWBK", FB="/drive_left/L_FBBK")
    T3 = [("VM", [(20.75, 27.35), (20.75, 27.05), (21.75, 27.05), (21.75, 27.35)], 0.25),
          ("VM", [(21.25, 27.35), (21.25, 27.05)], 0.25),
          ("VM", [(20.75, 27.05), (20.75, 26.3)], 0.25),
          ("CP", [(22.25, 27.35), (22.25, 26.3)], 0.25),
          ("CPH", [(22.75, 27.35), (22.75, 24.8)], 0.25),
          ("CPL", [(23.25, 27.35), (23.25, 25.7), (23.8, 25.15), (24.5, 25.15), (24.6, 24.8)], 0.25),
          ("SW", [(23.75, 27.35), (23.75, 26.9)], 0.25),
          ("FB", [(24.75, 27.35), (24.75, 26.9)], 0.25),
          ("VM", [(18.8, 26.05), (20.35, 26.05)], 0.4),
          ("VM3", [(21.0, 24.55), (20.35, 25.2), (20.35, 26.05)], 0.4)]     # C300's VM pad (U3 only: C400 is on the bottom)
    V3 = [("SW", (23.75, 26.9)), ("FB", (24.75, 26.9))]
    tr, vi = [], []
    for side in ("L", "R"):
        for k, pts, w in T3:
            if k == "VM3":
                if side == "R":
                    continue
                k = "VM"
            net = L[k] if side == "L" else L[k].replace("drive_left/L_", "drive_right/R_")
            if side == "R":
                pts = [(round(89.5 - x, 3), round(54.5 - y, 3)) for x, y in pts]
            tr.append(trk(net, F, pts, w))
        for k, c in V3:
            net = L[k] if side == "L" else L[k].replace("drive_left/L_", "drive_right/R_")
            if side == "R":
                c = (round(89.5 - c[0], 3), round(54.5 - c[1], 3))
            vi.append(via(net, c))
    tr += [trk("/drive_right/R_VM", F, [(69.15, 28.45), (68.9, 28.9), (68.3, 29.5), (68.3, 29.9)], 0.4),  # C403 VM -> C400
           trk("/drive_right/R_VM", B, [(68.3, 29.9), (68.9, 29.9)], 0.4)]                              # (bottom), via clear
    vi.append(via("/drive_right/R_VM", (68.3, 29.9), 0.45, 0.25))                                      # of the DRV_OFF lane
    return [dict(tag="U3/U4 charge pump + VM caps (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["6a U3/U4 charge pump"] = drive_caps()

# block 6b: motor outputs, top layer, 0.8 mm lanes (necked to 0.25 at the 0.5-pitch pins, both pins of a phase
# combed by a short bar); pin order already matches connector order on both sides, so nothing crosses.
# U3 (left side, x 19.3-19.9): L_A 13/14, L_B 16/17, L_C 19/20 west to JL1/JL2/JL3 (y 32.4): L_C straight into JL3,
# L_B turns down to JL2 inside L_A, L_A outermost to JL1.  U4 (right side, x 69.6-70.2): R_A straight into JR1, R_B up
# past JR1's corner into JR2, R_C climbs at x 71.0 (clear of JR2) into JR3.  The GND pins between the pairs (15/18)
# tie straight into the exposed pad.
def motor_outputs():
    tr = []
    for side, x_pin, x_bar, x_ep, pre in (("L", 19.6, 19.0, 20.4, "/drive_left/L_"), ("R", 69.9, 70.5, 69.1, "/drive_right/R_")):
        pins = {"A": (13, 14), "B": (16, 17), "C": (19, 20)}
        ys = {"L": {13: 28.25, 14: 28.75, 15: 29.25, 16: 29.75, 17: 30.25, 18: 30.75, 19: 31.25, 20: 31.75},
              "R": {13: 26.25, 14: 25.75, 15: 25.25, 16: 24.75, 17: 24.25, 18: 23.75, 19: 23.25, 20: 22.75}}[side]
        for ph, (p1, p2) in pins.items():
            net = pre + ph
            tr.append(trk(net, F, [(x_pin, ys[p1]), (x_bar, ys[p1]), (x_bar, ys[p2]), (x_pin, ys[p2])], 0.25))
        for p in (15, 18):
            tr.append(trk("GND", F, [(x_pin, ys[p]), (x_ep, ys[p])], 0.25))
    W = 0.8
    tr += [trk("/drive_left/L_C", F, [(19.0, 31.5), (16.6, 31.5), (16.2, 31.9)], W),
           trk("/drive_left/L_B", F, [(19.0, 30.0), (14.0, 30.0), (12.0, 32.0), (12.0, 32.4)], W),
           trk("/drive_left/L_A", F, [(19.0, 28.5), (10.0, 28.5), (7.8, 30.7), (7.8, 32.4)], W),
           trk("/drive_right/R_A", F, [(70.5, 26.0), (73.1, 26.0)], W),
           trk("/drive_right/R_B", F, [(70.5, 24.5), (71.1, 24.5), (72.3, 23.3), (72.6, 23.0), (73.1, 22.5)], W),
           trk("/drive_right/R_C", F, [(70.5, 23.0), (71.0, 22.5), (71.0, 19.8), (71.6, 19.2), (72.6, 18.7)], W)]
    return [dict(tag="motor outputs (fixed)", fixed=dict(tracks=tr, vias=[]))]


BLOCKS["6b motor outputs"] = motor_outputs()


# block 6c: VM trunks, top.  L_VM: R302's L_VM pad straight down into the VM cap cluster in front of U3, threaded
# between C301's and C300's GND pads (0.7 mm), with two 0.6/0.3 vias on the way to the bottom bulk caps (C308/C309,
# C302).  R_VM: R402's R_VM pad up to C400's via (which joins C403's VM pad on top and C400 on the bottom), plus a via
# at R402 for C402/C408 underneath.  The far bulk caps (C310, C409, C410) are joined by the router afterwards.
def vm_trunks():
    vl = pick_via("/drive_left/L_VM", (22.0, 22.75), 0.6, 0.3)          # beside C308's VM pad (J1 fills x < 20)
    vr = pick_via("/drive_right/R_VM", (67.0, 33.8), 0.6, 0.3)
    tr = [trk("/drive_left/L_VM", F, [(16.8, 21.8), (18.3, 23.3), (18.3, 25.9)], 0.7),
          trk("/drive_left/L_VM", F, [(17.0, 21.5), (vl[0] - 0.7, 21.5), vl], 0.6),
          trk("/drive_left/L_VM", B, [vl, (21.3, 22.1)], 0.6),
          trk("/drive_right/R_VM", F, [(67.2, 31.5), (68.3, 30.4), (68.3, 29.9)], 0.7),
          trk("/drive_right/R_VM", B, [(62.5, 31.4), (62.5, 31.93), (66.3, 31.93), (66.8, 32.43), (67.0, 32.6)], 0.3)]   # C408 -> C402
    vi = [via("/drive_left/L_VM", vl, 0.6, 0.3), via("/drive_right/R_VM", vr, 0.6, 0.3)]
    return [dict(tag="VM trunks (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["6c VM trunks"] = vm_trunks()

# block 6d: VM bulk caps joined to the trunks (0.5 mm; L3 allowed where it's free)
BLOCKS["6d VM bulk"] = auto("b6d_vm_bulk", w=0.5, via=0.6, drill=0.3, layers=[F, L3, B],
                            layer_cost={F: 1.0, B: 1.0, L3: 1.3}, via_cost=1.0, margin=4.0)

# block 6: U3 / U4 local (charge pump, AVDD, buck FB/SW): short cap hookups, top first; 0.25 leaves a 0.5-pitch pin
BLOCKS["6 U3/U4 local"] = auto("b6_drives_local", w=0.25, layers=[F, B], layer_cost={F: 1.0, B: 1.5}, via_cost=2.0)

# ---------------------------------------------------------------- fan-out of the other ICs (dog-bones)
def ic_fanout(ref, pairs_name, skip=("GND",), side_layer=None, depths=(0.5, 0.95, 1.4, 1.85, 2.3)):
    """Each pin of `ref` that still has an open connection to something > 3 mm away gets a stub straight out along
    its pad's long axis (away from the part's centre) to the nearest legal 0.4/0.2 via.  The open pins come from a
    frozen pair list (make_pairs.py over the board routed up to here)."""
    here = __import__("pathlib").Path(__file__).resolve().parent
    g = json.load(open(here / "out" / "route" / "geom.json"))
    pads = {p["num"]: p for p in g["pads"] if p["ref"] == ref}
    xs = [p["c"][0] for p in pads.values()]
    ys = [p["c"][1] for p in pads.values()]
    cx0, cy0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    want = {}
    for pr in json.load(open(here / "pairs" / f"{pairs_name}.json")):
        for e, o in ((pr["a"], pr["b"]), (pr["b"], pr["a"])):
            if e[0] == "pad" and e[1] == ref and pr["net"] not in skip and pr["dist"] > 3.0:
                want[e[2]] = pr["net"]
    sp = space()
    tracks, vias, fails = [], [], []
    for num, net in sorted(want.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        p = pads[num]
        x0_, y0_, x1_, y1_ = p["box"]
        cx, cy = p["c"]
        lay = side_layer or p["layers"][0]
        if (x1_ - x0_) >= (y1_ - y0_):                              # long along x: goes out left or right
            d = (1.0, 0.0) if cx > cx0 else (-1.0, 0.0)
            end = (x1_ if d[0] > 0 else x0_, cy)
        else:
            d = (0.0, 1.0) if cy > cy0 else (0.0, -1.0)
            end = (cx, y1_ if d[1] > 0 else y0_)
        side = (-d[1], d[0])
        best = None
        for depth in depths:
            for lat in (0.0, 0.25, -0.25, 0.5, -0.5):
                bend = (end[0] + d[0] * max(0.0, depth - 0.35), end[1] + d[1] * max(0.0, depth - 0.35))
                c = (round(bend[0] + d[0] * 0.35 + side[0] * lat, 3), round(bend[1] + d[1] * 0.35 + side[1] * lat, 3))
                pts = [end] + ([bend] if lat else []) + [c]
                if sp.via_ok(c, 0.4, 0.2, net) and sp.track_ok(pts, 0.15, lay, net):
                    best = (c, pts)
                    break
            if best:
                break
        if not best:
            fails.append(num)
            continue
        c, pts = best
        sp.add_via(c, 0.4, 0.2, net)
        sp.add_track(pts, 0.15, lay, net)
        vias.append(via(net, c))
        tracks.append(trk(net, lay, [(cx, cy)] + pts, 0.15))
    return [dict(tag=f"{ref} fan-out (fixed; {len(vias)} pins; no spot: {' '.join(fails)})",
                 fixed=dict(tracks=tracks, vias=vias))]


# block 7: fan-out of the drive / gate ICs' logic pins (the buses then run via-to-via, mostly on L3)
BLOCKS["7 IC fan-outs"] = ic_fanout("U2", "b7_open", skip=("GND", "W_SOA", "W_SOB", "W_SOC", "W_INHA", "W_INHB", "W_INHC",
                                                         "/weapon/W_INLA", "/weapon/W_INLB", "/weapon/W_INLC")) + ic_fanout("U3", "b7_open")


# block 7c: U4's escape, planned by hand (the generic fan-out found spots for 5 of 16 pins).
# Front row (y 21.8-22.4): INHC/INHB/INHA and DRV_OFF drop to vias just in front (y ~21.25); the three +3V3 pins between
# them drop between those vias to a second row (y 20.55) tied on the bottom; pin 23 (+3V3) to its own via; AVDD (25)
# straight into C405 (now standing in front of it); nFAULT (22) through a via into R401 (standing in front of it),
# whose other end joins C405.  Left side (x 62.8-63.4): two staggered via columns (x 62.55 / 62.0) for SPI, nCS and
# the current-sense outputs; AVDD (37) runs on top west, north along x 61.2 and east along y 19.9 into C405, where a
# via also takes it down to C406 on the bottom.
def u4_escape():
    tr, vi = [], []
    for pin_x, via_c, net, w in ((64.25, (64.25, 21.25), "R_INHC", 0.15), (65.25, (65.25, 21.25), "R_INHB", 0.15),
                                 (68.25, (68.25, 21.25), "+3V3", 0.2)):
        tr.append(trk(net, F, [(pin_x, 22.1), via_c], w))
        vi.append(via(net, via_c))
    tr += [trk("R_INHA", F, [(66.25, 22.1), (66.25, 21.55), (66.5, 21.3)], 0.15),
           trk("DRV_OFF", F, [(69.25, 22.1), (69.25, 21.55), (69.5, 21.3)], 0.15)]
    vi += [via("R_INHA", (66.5, 21.3)), via("DRV_OFF", (69.5, 21.3))]
    for x in (63.75, 64.75, 65.75):
        tr.append(trk("+3V3", F, [(x, 22.1), (x, 20.55)], 0.2))
    tr.append(trk("+3V3", F, [(63.75, 20.55), (65.75, 20.55)], 0.3))      # tie bar on top, one via at its east end
    vi.append(via("+3V3", (65.75, 20.55)))
    A = "/drive_right/R_AVDD"
    tr += [trk(A, F, [(67.25, 22.1), (67.25, 20.45)], 0.25),
           trk("R_nFAULT", F, [(68.75, 22.1), (68.75, 20.0)], 0.15),
           trk(A, F, [(68.75, 18.83), (68.35, 18.83), (68.05, 19.13), (68.05, 20.2), (67.8, 20.45)], 0.2),
           trk(A, F, [(66.6, 20.45), (66.9, 20.45)], 0.25),
           trk(A, B, [(66.6, 20.45), (67.25, 20.45)], 0.25),
           trk(A, F, [(63.1, 24.75), (61.2, 24.75), (61.2, 20.2), (61.5, 19.9), (66.6, 19.9), (66.6, 20.45)], 0.2)]
    vi += [via("R_nFAULT", (68.75, 20.8)), via(A, (66.6, 20.45))]
    left = {33: ("SPI_MISO", 62.55), 34: ("SPI_MOSI", 62.0), 35: ("SPI_SCK", 62.55), 36: ("R_nCS", 62.0),
            38: ("R_SOC", 62.0)}
    for pin, (net, x) in left.items():
        y = 22.75 + 0.5 * (pin - 33)
        tr.append(trk(net, F, [(63.1, y), (x, y)], 0.15))
        vi.append(via(net, (x, y)))
    # SOB (39) outside SOA (40): down the left of U4's corner into R81 / R80 standing below it
    tr += [trk("R_SOB", F, [(63.1, 25.75), (62.55, 25.75), (62.3, 26.0), (62.3, 27.92), (62.55, 28.17)], 0.15),
           trk("R_SOA", F, [(63.1, 26.25), (62.85, 26.5), (62.85, 27.55), (63.2, 27.9), (63.35, 27.9), (63.62, 28.17)], 0.15)]
    return [dict(tag="U4 escape (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["7c U4 escape"] = u4_escape()


# block 7d: U2's rear pins 37-42 (INH/INL A-C) drop into one row of six vias at 0.55 pitch just behind them (y 27.3):
# the bottom band there is only 1.1 mm deep (U2's thermal keep-out in front, the hall filter resistors R114-R116
# behind), so the row is spread slightly wider than the pins instead of staggered.  C28 moved back to make room.
def u2_rear_escape():
    tr, vi = [], []
    for k, (pin, net) in enumerate(((37, "W_INHA"), (38, "/weapon/W_INLA"), (39, "W_INHB"), (40, "/weapon/W_INLB"),
                                    (41, "W_INHC"), (42, "/weapon/W_INLC"))):
        x = 50.75 + 0.5 * k
        c = (round(52.0 + 0.55 * (k - 2.5), 3), 27.3)
        tr.append(trk(net, F, [(x, 26.6), (x, 26.95), c], 0.15))
        vi.append(via(net, c))
    return [dict(tag="U2 rear escape (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["7d U2 rear escape"] = u2_rear_escape()


# ---------------------------------------------------------------- block 8: east bus (L3), planned lanes
# Behind U2 (x 44 east) twelve 0.15 lanes at 0.3 pitch, y 27.8-31.1.  North: the U4-front group (DRV_OFF, nFAULT, INHA,
# INHB, INHC), whose ends at U1 are its top row / right column; south: the U4-left group (MISO, MOSI, SCK, nCS, SOC,
# SOB, SOA), whose west ends go round U1's south side.  At the east end, in order, so nothing crosses:
#   U4-front: north in columns x 58.45-59.65 (just east of U2 and phase A's vias), east in rows y 18.65-19.85 (just
#   behind the VBAT feed's rear edge), then down into U4's front-row vias between the +3V3 vias (INHA at 0.127 to pass
#   the +3V3 / AVDD vias).
#   U4-left: on east, north in columns x 60.0-61.8, east in rows at the via heights into U4's left via columns.
EAST_X0 = 44.0
EAST_FRONT = [("DRV_OFF", (69.5, 21.3)), ("R_nFAULT", (68.75, 20.8)), ("R_INHB", (65.25, 21.25)),
              ("R_INHA", (66.5, 21.3)), ("R_INHC", (64.25, 21.25))]
EAST_FRONT_ROW = {"DRV_OFF": 18.65, "R_nFAULT": 18.95, "R_INHB": 19.4, "R_INHA": 19.9, "R_INHC": 20.25}
EAST_LEFT = [("SPI_MISO", 22.95, (62.55, 22.75)), ("SPI_MOSI", 23.25, (62.0, 23.25)), ("SPI_SCK", 23.75, (62.55, 23.75)),
             ("R_nCS", 24.25, (62.0, 24.25))]
SOB_F, SOA_F = "/mcu/R_SOB_F", "/mcu/R_SOA_F"
EAST_CSA = [(SOB_F, (62.55, 29.19), (62.55, 29.8)), (SOA_F, (63.62, 29.19), (63.62, 29.8))]   # R81 / R80 pad 2, via near


def east_lane_y():
    ys = {}
    for k, (net, _) in enumerate(EAST_FRONT):
        ys[net] = 27.8 + 0.3 * k
    for k, (net, _, _) in enumerate(EAST_LEFT):
        ys[net] = 27.8 + 0.3 * (len(EAST_FRONT) + k)
    for k, (net, _, _) in enumerate(EAST_CSA):
        ys[net] = 27.8 + 0.3 * (len(EAST_FRONT) + len(EAST_LEFT) + k)
    return {n: round(y, 3) for n, y in ys.items()}


def east_bus():
    ys = east_lane_y()
    tr, vi = [], []
    for k, (net, v) in enumerate(EAST_FRONT):
        cx = round(58.45 + 0.3 * k, 3)
        row = EAST_FRONT_ROW[net]                             # (clear of cell A's GND vias; room for INHB's hop via)
        pts = [(EAST_X0, ys[net]), (cx, ys[net]), (cx, row)]
        if net == "R_INHA":
            tr.append(trk(net, L3, pts + [(66.17, row), (66.17, 20.9), v], 0.127))
            continue
        if net == "R_INHB":                                    # hop under INHA's row on the bottom, into its via
            tr.append(trk(net, L3, pts + [(65.25, row)], 0.15))
            tr.append(trk(net, B, [(65.25, row), v], 0.15))
            vi.append(via(net, (65.25, row)))
            continue
        pts += [(v[0], row), v]
        tr.append(trk(net, L3, pts, 0.15))
    for k, (net, row_y, v) in enumerate(EAST_LEFT):
        cx = round(60.0 + 0.3 * k, 3)
        pts = [(EAST_X0, ys[net]), (cx, ys[net]), (cx, row_y)]
        if net == "SPI_MISO":                                   # over the MOSI via to the MISO via
            pts += [(61.5, row_y), (61.8, 22.65), (62.35, 22.65), v]
        else:
            pts += [v]
        tr.append(trk(net, L3, pts, 0.15))
    for net, pad, near in EAST_CSA:                             # outer lanes: straight on east, up into the via
        v = pick_via(net, near)
        tr.append(trk(net, F, [pad, v], 0.15))
        tr.append(trk(net, L3, [(EAST_X0, ys[net]), (v[0], ys[net]), v], 0.15))
        vi.append(via(net, v))
    return [dict(tag="east bus lanes (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["8a east bus lanes"] = east_bus()

# block 8b: the lanes' west ends, planned like the east end.
#   North group (DRV_OFF, nFAULT, INHB): north in columns x 43.35 / 43.05 / 42.75 up U1's east side (clear of U1 pin 24's via), west in rows y 20.5 /
#   20.8 / 21.1 above U1's top-row vias (INHB innermost: it ends first, at x 36.0), down into their vias.
#   INHA / INHC: into U1's field through the gap under its +3V3A vias (y 28.25 / 28.6); INHA up just inside the right
#   via column to its via, INHC west past the north of the R_S3 via to its via.
#   South group: south in columns x 41.9-43.4, west in rows under U1 (y 31.3-33.4).  The two CSA lanes are outermost and
#   drop first, into vias beside their caps C90 / C91 at U1's rear edge.  MISO turns in first, north into U1's
#   field to its fan-out via.  U1's west-side pins run the other way round (SCK south of MISO and MOSI, nCS north), so
#   nCS -- the southmost row -- leaves on the top layer just behind U1's rear pins and runs north under J2's body,
#   between two of its pins, to a via in the field that pin 57 reaches on the bottom; SCK and MOSI go on west and
#   north in columns x 29.7 / 30.0 over U1's west pins and peel off west to vias beside pins 52 / 54 (where R80/R81
#   used to be).
EAST_SOUTH_ROW = {"SPI_MISO": 31.3, "SPI_MOSI": 32.05, "SPI_SCK": 32.35, "R_nCS": 32.8, SOB_F: 33.1, SOA_F: 33.4}


def east_west_ends():
    ys = east_lane_y()
    tr, vi = [], []
    x0 = EAST_X0
    tr += [trk("DRV_OFF", L3, [(x0, ys["DRV_OFF"]), (43.35, ys["DRV_OFF"]), (43.35, 20.5), (29.45, 20.5), (29.45, 21.25)], 0.15),
           trk("R_nFAULT", L3, [(x0, ys["R_nFAULT"]), (43.05, ys["R_nFAULT"]), (43.05, 20.8), (33.25, 20.8), (33.25, 21.55)], 0.15),
           trk("R_INHB", L3, [(x0, ys["R_INHB"]), (42.75, ys["R_INHB"]), (42.75, 21.1), (36.0, 21.1), (36.0, 21.55)], 0.15),
           trk("R_INHA", L3, [(x0, ys["R_INHA"]), (40.5, ys["R_INHA"]), (40.05, 28.25), (39.45, 28.25), (39.45, 26.7),
                              (39.65, 26.5), (39.95, 26.5)], 0.15),
           trk("R_INHC", L3, [(x0, ys["R_INHC"]), (40.35, ys["R_INHC"]), (39.95, 28.6), (38.2, 28.6), (37.85, 28.25),
                              (35.95, 28.25), (35.75, 28.35)], 0.15)]
    south = [n for n, _, _ in EAST_LEFT] + [n for n, _, _ in EAST_CSA]
    head = {}
    for k, net in enumerate(south):                     # lane -> column south -> row west (to its first bend)
        cx = round(41.9 + 0.3 * k, 3)
        head[net] = [(x0, ys[net]), (cx, ys[net]), (cx, EAST_SOUTH_ROW[net])]
    row = EAST_SOUTH_ROW
    # CSA lanes: down beside their caps, bottom stubs up into the caps' pads; U1.34/35 down into the same pads
    vA = pick_via(SOA_F, (40.77, 34.15))
    vB = pick_via(SOB_F, (38.6, 34.25))
    tr += [trk(SOA_F, L3, head[SOA_F] + [(vA[0], row[SOA_F]), vA], 0.15), trk(SOA_F, B, [vA, (40.77, 33.4)], 0.15),
           trk(SOB_F, L3, head[SOB_F] + [(vB[0], row[SOB_F]), vB], 0.15), trk(SOB_F, B, [vB, (38.77, 33.4)], 0.15),
           trk(SOA_F, B, [(38.75, 31.68), (38.75, 32.77), (40.4, 32.77), (40.77, 33.14), (40.77, 33.4)], 0.15),
           trk(SOB_F, B, [(38.25, 31.68), (38.25, 33.4), (38.77, 33.4)], 0.15)]
    vi += [via(SOA_F, vA), via(SOB_F, vB)]
    # MISO: north into the field between the W_EN / W_INHC vias, west to its fan-out via
    tr.append(trk("SPI_MISO", L3, head["SPI_MISO"] + [(33.75, row["SPI_MISO"]), (33.75, 27.8), (33.45, 27.5),
                                                      (31.4, 27.5)], 0.15))
    # SCK / MOSI: columns over U1's west pins, west into vias beside pins 52 / 54
    v_sck = pick_via("SPI_SCK", (28.25, 28.25))
    v_mosi = pick_via("SPI_MOSI", (27.6, 27.2))
    tr += [trk("SPI_SCK", L3, head["SPI_SCK"] + [(29.7, row["SPI_SCK"]), (29.7, v_sck[1]), v_sck], 0.15),
           trk("SPI_SCK", B, [(29.82, 28.25), (v_sck[0] + 0.3, 28.25), v_sck], 0.15),
           trk("SPI_MOSI", L3, head["SPI_MOSI"] + [(30.0, row["SPI_MOSI"]), (30.0, v_mosi[1]), v_mosi], 0.15),
           trk("SPI_MOSI", B, [(29.82, 27.25), (v_mosi[0] + 0.3, 27.25), v_mosi], 0.15)]
    vi += [via("SPI_SCK", v_sck), via("SPI_MOSI", v_mosi)]
    # nCS: up to the top just behind U1's rear pins (between caps C62 / C80), north under J2's body through the gap
    # between its pins 2 and 3 to a via just past them; pin 57 reaches it on the bottom, round the inside of its
    # neighbours' fan-out vias
    h1 = (33.75, row["R_nCS"])
    v_ncs = pick_via("R_nCS", (32.45, 28.7))
    tr += [trk("R_nCS", L3, head["R_nCS"] + [h1], 0.15),
           trk("R_nCS", F, [h1, (32.3, 31.35), (32.3, 28.85), v_ncs], 0.15),
           trk("R_nCS", B, [(29.82, 25.75), (v_ncs[0], 25.75), v_ncs], 0.15)]
    vi += [via("R_nCS", h1), via("R_nCS", v_ncs)]
    reqs = [dict(tag="east bus west ends (fixed)", fixed=dict(tracks=tr, vias=vi))]
    # CSA C: R_SOC from U4's via to R82 (over U1's right column), R82's output to U1.25 and its cap C92
    q = dict(via_cost=1.0, margin=4.0, w=0.15)
    reqs += [dict(tag="R_SOC U4 to R82", net="R_SOC", a=("via", 62.0, 25.25), b=("pad", "R82", "1"),
                  layers=[B, F, L4], layer_cost={B: 1.0, F: 1.5, L4: 1.6}, avoid=[[B, 54.5, 25.9, 62.3, 31.0]], **q),
             # (bottom, kept along the top of the channel under U2's rear: U10's outputs nest below it.  Not L4:
             #  it would cross the U2 rear bus there -- the INL lanes start south of this line and end north of it)
             dict(tag="R_SOC_F R82 to U1", net="/mcu/R_SOC_F", a=("pad", "R82", "2"), b=("pad", "U1", "25"),
                  layers=[B, F], layer_cost={B: 1.0, F: 1.3}, **q),
             dict(tag="R_SOC_F R82 to C92", net="/mcu/R_SOC_F", a=("pad", "R82", "2"), b=("pad", "C92", "1"),
                  layers=[L4, F, B], layer_cost={L4: 1.0, F: 1.3, B: 3.0},
                  avoid=[[B, 41.9, 23.2, 42.9, 26.7], [B, 42.0, 22.6, 45.3, 23.2]], **q)]    # (+ W_VA's lane under C92)   # over L4: keeps U1's east edge
                                                                                     # clear on the bottom (pin 24)
    return reqs + [dict(r, retry=True, margin=8.0, via_cost=0.6) for r in reqs if "fixed" not in r]


BLOCKS["8b east bus west ends"] = east_west_ends()

# block 8: logic and rails, via to via: L3 is the main layer in the rear half (outer layers cost more), fan-out vias
# are free layer changes, shortest first
# (tried as one greedy auto block: 112 of 230 routed but L3 came out as spaghetti that fragments the layer; not kept.
#  The buses get planned lanes instead; this block is only for the short leftovers once they're in.)

# block 7b: U2's front-left current-sense outputs (pins 23/24/25), boxed in by phase C's escape.  W_SOC and W_SOB drop
# straight to vias just in front of pins 23/24 (the L3 band there is free since SNC's lane moved to y 17.95) and run west
# on L3 between SNC's lane (y 17.9, stair via tucked into the VBAT feed's edge) and phase C's (y 18.2 / 18.6); W_SOA
# leaves pin 25 west at y 20.515 between the SHC stair via and the VREF trace.  The router takes all three on to U1.
def u2_sense_escape():
    tr = [trk("W_SOC", F, [(51.25, 19.3), (51.25, 18.4)], 0.15),
          trk("W_SOB", F, [(50.75, 19.3), (50.75, 18.7)], 0.15),
          trk("W_SOC", L3, [(51.25, 18.4), (51.05, 18.2), (47.0, 18.2), (46.7, 18.5)], 0.15),   # off the pour edge
          trk("W_SOB", L3, [(50.75, 18.7), (50.65, 18.6), (47.2, 18.6)], 0.15),
          trk("W_SOA", F, [(49.8, 20.25), (49.6, 20.25), (49.4, 20.53), (47.6, 20.53)], 0.127)]
    tr.append(trk("W_SOA", B, [(37.25, 20.32), (37.25, 18.95)], 0.15))    # U1 pin 12 straight out to its via
    vi = [via("W_SOC", (51.25, 18.4)), via("W_SOB", (50.75, 18.7)), via("W_SOA", (37.25, 18.95))]
    rt = dict(layers=[F, L3, B], layer_cost={L3: 1.0, F: 1.4, B: 1.4}, via_cost=1.0, margin=4.0, w=0.15,
              avoid=[["*", 46.3, 20.95, 50.0, 22.1], ["*", 47.8, 24.0, 50.0, 24.95],   # U2's W_nFAULT / W_EN exits (12a)
                     ["*", 41.9, 25.1, 42.75, 26.1]])                                      # U1 pin 24's via (12b1)
    return [dict(tag="U2 sense escape (fixed)", fixed=dict(tracks=tr, vias=vi)),
            dict(tag="W_SOC to U1", net="W_SOC", a=("pt", 46.7, 18.5, L3), b=("via", 39.25, 30.45), **rt),
            dict(tag="W_SOB to U1", net="W_SOB", a=("pt", 47.2, 18.6, L3), b=("via", 37.5, 21.55), **rt),
            dict(tag="W_SOA to U1", net="W_SOA", a=("pt", 47.6, 20.53, F), b=("via", 37.25, 18.95), **rt)] + [
            dict(tag=t, net=n, a=a, b=b, retry=True, **dict(rt, margin=8.0, via_cost=0.6))
            for t, n, a, b in (("W_SOC to U1", "W_SOC", ("pt", 46.7, 18.5, L3), ("via", 39.25, 30.45)),
                               ("W_SOB to U1", "W_SOB", ("pt", 47.2, 18.6, L3), ("via", 37.5, 21.55)),
                               ("W_SOA to U1", "W_SOA", ("pt", 47.6, 20.53, F), ("via", 37.25, 18.95)))]


BLOCKS["7b U2 sense escape"] = u2_sense_escape()

# block 9a: BMS corner (U8, J4 balance header, R7-R11, C4-C11), a self-contained local group: router with frozen
# pairs, checked by eye.  Bottom-left; the L3 under it is free.
# (The two motor-sensor clusters were tried the same way and came out as detours through U1's field: their placement
#  boxes them in -- J2's pins face U1's fan-out via row with U9 right behind it, J3's filters sit in a one-part band
#  under the east bus -- so they get re-placed and planned instead.)
BLOCKS["9a BMS corner"] = auto("b9_bms", layers=[B, F, L3], layer_cost={B: 1.0, F: 1.3, L3: 1.3})
if os.environ.get("TRIAL") == "1":         # measurement only: every remaining signal pair, shortest first
    BLOCKS["10 trial"] = auto("b10_trial", layers=[F, B, L3], layer_cost={F: 1.0, B: 1.1, L3: 1.2}, via_cost=1.0)
# block 11a: the bottom-side logic under the bridge (U6 INL gates, U7 INA239, U14 ARM buffer, the MCU-pin filters
# north of U1): local pairs only, shortest first, bottom then top.  The long legs (U2 <-> U6, U1's south pins -> U6,
# INA_nCS, the west runs to J1/R33) are planned separately.
BLOCKS["11a NW logic local"] = auto("b11a_nw_local", layers=[B, F], layer_cost={B: 1.0, F: 2.0}, via_cost=1.5)
for _r in BLOCKS["11a NW logic local"]:      # R53 -> R117 (10 mm) on L4, not on top past TP7 / U2's W_EN exit
    if _r["net"] == "R_MTEMP" and "R53-R117" in _r["tag"]:
        _r.update(layers=[L4, B], layer_cost={L4: 1.0, B: 1.5}, via_cost=1.0)
# block 12a: U2's west-side logic pins 28 (W_nFAULT) and 33 (W_EN), which the generic fan-out found no spot for:
# straight west on top between the mode/IDRIVE/VDS resistors to a via each (the router takes them on from there).
def u2_west_escape():
    # pin 28: the gap between C23 (bottom 21.41) and R44 (top 21.93) is centred on y 21.67, not on the pin
    v28 = (47.15, 21.2)                                # fixed (a pick drifts with the router routes of block 7b)
    # pin 33: under the VDS trace (y 24.1), clear of pin 34's pad
    v33 = (48.3, 24.55)
    tr = [trk("W_nFAULT", F, [(50.0625, 21.75), (49.7, 21.67), (v28[0] + 0.35, 21.67), v28], 0.15),
          trk("W_EN", F, [(50.0625, 24.25), (49.55, 24.25), (49.35, 24.45), (v33[0], 24.45), v33], 0.15)]
    vi = [via("W_nFAULT", v28), via("W_EN", v33)]
    return [dict(tag="U2 west logic escape (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["12a U2 west escape"] = u2_west_escape()


# block 12a2: U6 (INL AND gates) escape.  Its input row (pins 1-7, y 11.36) faces a row of VBAT stitching vias
# and R63's VBAT trace, so the signal pins drop inward instead: short bottom stubs to vias between U6's two pin rows
# (clear of the stitching columns at x 27.8 / 30.8 and the W_ARM_S tie down x 29.85); L4 takes them from there.
def u6_escape():
    # On top, RS4's VBAT pad (x 28.15-30.25, y 7-11) sits over U6's middle and its stitching vias run down x 30.8
    # (y 7.0-9.4): between the rows only x ~31.1-33 takes vias.  Pins 1-3 stagger there, pin 4 just north of the
    # stitching column; pins 3 and 6 drop south, pin 6 into the gap of the VBAT via row at y 12.8 (x 28.6 / 30.6),
    # pin 3 just east of it (so W_INLB, coming in from the north-east, passes north of W_INLA's via).
    esc = (("W_INLA_M", [(32.45, 11.36), (32.45, 10.6), (32.7, 10.35)], (32.7, 8.55)),
           ("W_ARM_S", [(31.8, 11.36), (31.8, 10.6), (32.05, 10.35)], (32.05, 9.3)),
           ("/weapon/W_INLA", [(31.15, 11.36), (31.15, 12.1), (31.5, 12.45)], (31.5, 12.95)),
           ("W_INLB_M", [(30.5, 11.36), (30.5, 10.6)], (30.85, 10.25)),
           ("/weapon/W_INLB", [(29.2, 11.36), (29.2, 12.1), (29.6, 12.5)], (29.6, 12.9)))
    tr, vi = [], []
    for net, pts, v in esc:
        tr.append(trk(net, B, pts + [v], 0.15))
        vi.append(via(net, v))
    # R63 (VBAT_SNS divider top) takes its own VBAT via beside it (the L3 VBAT feed is under it) instead of a trace
    # west under U6's input row to the stitching via: that strip is where W_INLA drops and W_INLB passes
    tr.append(trk("VBAT", B, [(33.95, 12.49), (34.6, 12.49)], 0.3))
    vi.append(via("VBAT", (34.6, 12.49), 0.45, 0.25))
    # W_ARM_S: pins 5 and 10 are tied by the bottom track down x 29.85; pin 2 joins that tie on L4 through a via at
    # the tie's pin-10 end (clear of RS4's pad), the L4 hop passing south of the stitching column
    a5 = (29.85, 6.62)
    tr.append(trk("W_ARM_S", L4, [(32.05, 9.3), (31.5, 8.75), (31.5, 6.35), (30.1, 6.35), a5], 0.15))
    vi.append(via("W_ARM_S", a5))
    return [dict(tag="U6 escape (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["12a2 U6 escape"] = u6_escape()


# block 12b: the U1 hub nets that cross U1's field or leave U2's enclosed region (W_INH/INL, W_EN, W_nFAULT, R_S,
# L_S3, MB_TX/RX, INA_nCS, W_INLx_M).  L4 is the long-haul layer: empty board-wide (under U1's field and under the
# VBAT feed too), so these run there nearly straight; longest first so they take the direct lines.
U2_REAR = {"W_INHA": (50.625, 27.3), "/weapon/W_INLA": (51.175, 27.3), "W_INHB": (51.725, 27.3),
           "/weapon/W_INLB": (52.275, 27.3), "W_INHC": (52.825, 27.3), "/weapon/W_INLC": (53.375, 27.3)}


# block 12b0: U2's rear group as one L4 bus from its via row (block 7d) -- the INH lines to U1 (INHC to its south
# via row, INHB / INHA to its top), then the INL lines to U6's escape vias in the NW.  L4 only (the ends are vias).
def u2_rear_bus():
    # U1 pins 8 / 9 straight out north to staggered vias (pin 9 had no fan-out spot; pin 8's is inside U1's field,
    # which is sealed on L4 by the fan-out via ring as on L3)
    # INHA's lane arrives north of INHB's: INHA's via further out (north of pin 8), INHB's just off pin 9
    v9 = (35.8, 19.3)
    v8 = (35.3, 18.6)
    fx = [dict(tag="U1 pins 8/9 escape + U2 rear fan-out (fixed)",
               fixed=dict(tracks=[trk("W_INHB", B, [(35.75, 20.32), v9], 0.15),
                                  trk("W_INHA", B, [(35.25, 20.32), (35.25, 18.9), v8], 0.15)],
                          vias=[via("W_INHB", v9), via("W_INHA", v8)]))]
    # lane order from the via row (0.55 pitch: on L4 each via leaves only north or south): INHC south, INHA straight
    # west from the westmost via, the rest north with INLA innermost -- routed inside-out
    ends = {"W_INHC": ("via", 34.25, 28.7), "W_INHA": ("via", v8[0], v8[1]), "/weapon/W_INLA": ("via", 31.5, 12.95),
            "W_INHB": ("via", v9[0], v9[1]), "/weapon/W_INLB": ("via", 29.6, 12.9),
            "/weapon/W_INLC": ("pad", "U6", "8")}
    # hand fan-out from the row: INHB / INHC down, the INL lines up to staggered lanes, all turned west
    # (lanes N->S: INLC, INLB, INLA | INHA | INHB, INHC -- the INL lines all go on past U1's top to U6, and INHA
    #  ends further out than INHB, so nothing crosses)
    fan = {"W_INHB": [(51.725, 27.95), (50.7, 27.95)], "W_INHC": [(52.825, 28.25), (51.0, 28.25)],
           "/weapon/W_INLA": [(51.175, 26.75), (50.3, 26.75)], "/weapon/W_INLB": [(52.275, 26.45), (50.6, 26.45)],
           "/weapon/W_INLC": [(53.375, 26.15), (50.9, 26.15)]}
    fx[0]["fixed"]["tracks"] += [trk(n, L4, [U2_REAR[n]] + pts, 0.15) for n, pts in fan.items()]
    start = {n: ("pt", pts[-1][0], pts[-1][1], L4) for n, pts in fan.items()}
    start["W_INHA"] = ("via",) + U2_REAR["W_INHA"]
    q = dict(layers=[L4, B], layer_cost={L4: 1.0, B: 3.0}, via_cost=1.0, margin=5.0, w=0.15)
    order = ["W_INHA", "W_INHB", "W_INHC", "/weapon/W_INLA", "/weapon/W_INLB", "/weapon/W_INLC"]   # inside-out
    U1_L4 = ["In3.Cu", 28.8, 20.9, 41.9, 32.6]      # U1's footprint on L4: kept for the nets that must cross U1
    rq = [dict(tag=f"{n} U2 rear bus", net=n, a=start[n], b=ends[n], **q,
               **({"avoid": [U1_L4]} if "INL" in n else {})) for n in order]
    return fx + rq + [dict(r, retry=True, margin=10.0, via_cost=0.7, layers=[L4, B, F, L3],
                           layer_cost={L4: 1.0, B: 1.5, F: 1.5, L3: 1.5}) for r in rq]


BLOCKS["12b0 U2 rear bus"] = u2_rear_bus()


# block 12b1: pads with no reachable via beside them get a short outer-layer stub to the nearest legal via spot
# ("drop"), so the hub routes can start on L4 from there: U10 pin 5 (R_S2, under the bus's east-end L3 columns),
# U1 pin 24 (L_S3, east side, no fan-out spot), U9 pin 2 (L_S3, in the sensor island on top).
ESCAPES = [("L_S3", ("pad", "U9", "2"), [F])]
BLOCKS["12b1 pad escapes"] = [dict(tag="U1 pin 24 escape (fixed)", fixed=dict(   # between U1's pads and C66, under R82's pad gap
    tracks=[trk("L_S3", B, [(41.175, 25.75), (42.1, 25.75), (42.32, 25.6)], 0.15)], vias=[via("L_S3", (42.32, 25.6))]))] + [
    dict(tag=f"{n} {e[1]}.{e[2]} escape", net=n, a=e, b=("drop",), layers=ls, margin=4.0, w=0.15) for n, e, ls in ESCAPES]


def hub_nets():
    here = __import__("pathlib").Path(__file__).resolve().parent
    # U10's two top-row outputs leave west along U10's south side, nested: R_S2 (westmost pin) outermost, first
    first = os.environ.get("HUBFIRST", "R_S2,R_S1").split(",")
    pairs = sorted(json.load(open(here / "pairs" / "b12_hub.json")),
                   key=lambda p: (first.index(p["net"]) if p["net"] in first else len(first), -p["dist"]))
    pairs = [p for p in pairs if not (p["net"] in U2_REAR and (p["a"][1] == "U2" or p["b"][1] == "U2" or
                                                                p["net"] == "W_INHC"))]
    q = dict(layers=[L4, B, F, L3], layer_cost={L4: 1.0, B: 1.4, F: 1.5, L3: 1.6}, via_cost=1.0, margin=4.0,
             via_through_pours=True)
    out = [dict(tag=f"{p['net']} {p['a'][1]}-{p['b'][1]}", net=p["net"], a=tuple(p["a"]), b=tuple(p["b"]), **q)
           for p in pairs]
    return out + [dict(r, retry=True, margin=10.0, via_cost=0.7) for r in out]


BLOCKS["12b hub nets"] = hub_nets()
FIELD_L3 = ["In2.Cu", 30.9, 21.9, 39.8, 30.3]        # U1's L3 via field: kept for the nets that must cross U1
if os.environ.get("TRIAL") == "west":
    BLOCKS["10 trial west"] = auto("b10_west", first=() and (
        "L_INHC", "L_nFAULT", "L_INHA", "/mcu/BOOT0", "L_INHB", "L_nCS", "SPI_SCK", "SPI_MOSI", "SPI_MISO",
        "/mcu/SWDIO", "/mcu/SWCLK", "L_SOA", "L_SOB", "L_SOC", "/mcu/L_SOA_F", "/mcu/L_SOB_F"),
        layers=[B, F, L3], layer_cost={B: 1.0, F: 1.3, L3: 1.2}, via_cost=1.0, avoid=[FIELD_L3])
if os.environ.get("TRIAL") == "hard":       # feasibility: the U1 crossers alone, longest first, any layer
    _h = auto("b12_hard", layers=[F, B, L3, L4], layer_cost={F: 1.0, B: 1.0, L3: 1.0, L4: 1.0}, via_cost=0.8, margin=10.0)
    BLOCKS["12 trial hard"] = sorted([r for r in _h if not r.get("retry")], key=lambda r: 0) + [r for r in _h if r.get("retry")]
if os.environ.get("TRIAL") == "nw":
    BLOCKS["11 trial nw"] = auto("b11_nw", first=("INA_nCS", "W_INLB_M", "W_INLC_M", "W_INLA_M", "/mcu/VBAT_SNS",
                                                 "R_MTEMP", "W_ARM_S", "/mcu/NRST", "W_nFAULT", "DRV_OFF"),
                                 layers=[B, F, L3], layer_cost={B: 1.0, F: 1.3, L3: 1.3}, via_cost=1.0)

# block 4: every GND pad still off the plane gets its own via to L2 (short stub, nearest legal spot)
def gnd_drops(name):
    here = __import__("pathlib").Path(__file__).resolve().parent
    seen, out = set(), []
    for p in json.load(open(here / "pairs" / f"{name}.json")):
        for e in (p["a"], p["b"]):
            if e[0] == "pad" and tuple(e) not in seen:
                seen.add(tuple(e))
                out.append(dict(tag=f"GND via {e[1]}.{e[2]}", net="GND", a=tuple(e), b=("drop",), w=0.3,
                                via=0.45, drill=0.25, layers=[F, B], margin=1.5))
    return out


BLOCKS["4 GND pad vias"] = gnd_drops("b4_gnd")

# survey (not kept): auto("b9_rest") over everything still open after block 3 routed ~165 of 272 pairs greedily,
# failed ~110 (MCU fan-out, +3V3, weapon logic, drives) and left clearance errors: the greedy one-net-at-a-time
# router has hit its limit in the dense logic areas; the rest needs planned blocks or rip-up-and-reroute.

# Hand-placed escapes are reservations: they go in right after block 7d, ahead of every router block, so the router
# routes around them instead of drifting into them from build to build (they used to be applied late, as block 12).
def _split_fixed(name):
    fx = [r for r in BLOCKS[name] if "fixed" in r]
    BLOCKS[name] = [r for r in BLOCKS[name] if "fixed" not in r]
    return fx


_reserve = {"7e U2 west escape": BLOCKS.pop("12a U2 west escape"), "7f U6 escape": BLOCKS.pop("12a2 U6 escape"),
            "7g U1 pins 8/9 + U2 rear fan-out": _split_fixed("12b0 U2 rear bus"),
            "7h U1 pin 24 escape": _split_fixed("12b1 pad escapes"),
            # W_VA: U1 pin 18 straight east on the bottom under C92 (R_SOC_F's cap) to its filter cap C41
            "7i U1 pin 18 to C41": [dict(tag="U1 pin 18 to C41 (fixed)", fixed=dict(tracks=[
                trk("W_VA", B, [(41.175, 22.75), (42.2, 22.75), (42.35, 22.9), (44.45, 22.9), (44.95, 22.4), (44.95, 22.23)],
                    0.15)], vias=[]))]}
_order = {}
for _k, _v in BLOCKS.items():
    _order[_k] = _v
    if _k == "7d U2 rear escape":
        _order.update(_reserve)
BLOCKS.clear()
BLOCKS.update(_order)
# block 12d: what the NW bottom-side block (11a) and the hub block left open north of the east bus, frozen after 12c;
# L4 allowed now that the U2 rear bus has its lanes (R23/R25, the W_VA/W_VB divider bottoms west of U1, stay put:
# their runs to the east side go on L4)
BLOCKS["12d NW leftovers"] = auto("b12d_nw_left", layers=[B, F, L4], layer_cost={B: 1.0, F: 1.4, L4: 1.2}, via_cost=1.0,
                                 via_through_pours=True)    # hops to L4 through the VBAT pours (the pour clears)
# R_SOC (U4 -> R82 over U1's east side) crosses the U2 rear bus's INL lanes whatever it does: route it after them
_soc = [r for r in BLOCKS["8b east bus west ends"] if r.get("net") == "R_SOC"]
BLOCKS["8b east bus west ends"] = [r for r in BLOCKS["8b east bus west ends"] if r.get("net") != "R_SOC"]
_order = {}
for _k, _v in BLOCKS.items():
    if _k == "12d NW leftovers":
        continue
    _order[_k] = _v
    if _k == "12b hub nets":
        _order["12c R_SOC"] = _soc
        _order["12d NW leftovers"] = BLOCKS["12d NW leftovers"]
        _order["12e rest"] = auto("b12e_rest", layers=[B, F, L4, L3], layer_cost={B: 1.0, F: 1.2, L4: 1.0, L3: 1.6},
                                  via_cost=0.8, margin=8.0, via_through_pours=True)
BLOCKS.clear()
BLOCKS.update(_order)

if __name__ == "__main__":
    upto = sys.argv[2] if len(sys.argv) > 2 else None
    out = []
    for name, reqs in BLOCKS.items():
        out += reqs
        if upto and name.startswith(upto):
            break
    json.dump(out, open(sys.argv[1], "w"), indent=0)
    print(f"{len(out)} requests")
