"""Routing blocks, in order.  Each request: net, a, b (endpoints: ("pad", ref, num) | ("via", x, y) | ("pt", x, y, layer)),
layers, layer_cost, via_cost, margin (search window around the endpoints, mm), optional w/clr overrides, tag.
A request with "fixed" = {"tracks": [...], "vias": [...]} passes hand-planned geometry straight through.
Coordinates: board-local mm (front-left corner, y toward the rear)."""
import json
import sys

F, L3, B = "F.Cu", "In2.Cu", "B.Cu"
BLOCKS = {}


_SPACE = None


def space():
    """Clearance model of the base board (geo.Space) for picking hand-placed via spots."""
    global _SPACE
    if _SPACE is None:
        here = __import__("pathlib").Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        from geo import Space
        _SPACE = Space(json.load(open(here / "out" / "route" / "geom.json")))
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
STAIR = {"SNC": (47.5, 18.55), "SLC": (48.05, 19.05), "GLC": (48.6, 19.72), "C": (49.2, 20.1)}
T_ += [trk(N("SNC"), L3, [(51.75, R2), (51.3, 18.55), STAIR["SNC"]], 0.2),
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
CP = [trk("/weapon/U2_VCP", F, [(57.2, 23.75), (57.7, 23.75), (57.95, 24.0), (60.45, 24.0), (60.45, 23.4)], 0.2),
      trk("/weapon/U2_CPH", F, [(57.2, 24.25), (57.7, 24.25), (57.95, 24.5), (60.22, 24.5), (60.22, 25.0)], 0.2),
      trk("/weapon/U2_CPL", F, [(57.2, 24.75), (57.7, 24.75), (57.95, 25.0), (58.5, 25.0)], 0.2)]
b2 = [
    dict(tag="charge pump lanes (fixed)", fixed=dict(tracks=CP, vias=[])),
    pp("SW U2-D2", "/weapon/BUCK_SW", "U2.45", "D2.1", w=0.3, layers=[F]),        # 0.3: leaves a 0.5-pitch pin
    pp("SW D2-L1", "/weapon/BUCK_SW", "D2.1", "L1.1", w=0.6, layers=[F]),
    pp("SW C28", "/weapon/BUCK_SW", "C28.2", "D2.1", w=0.4, layers=[F]),
    pp("CB", "/weapon/BUCK_CB", "U2.44", "C28.1", w=0.3),
    pp("VIN C27", "VBAT", "C27.1", "U2.47", w=0.3, layers=[F]),
    pp("VM C24", "VBAT", "C24.1", "U2.6", w=0.4, layers=[F]),
    pp("VM 6-7", "VBAT", "U2.6", "U2.7", w=0.25, layers=[F]),
    pp("VCP cap VM", "VBAT", "C21.2", "C24.1", w=0.3),
    pp("DVDD", "/weapon/U2_DVDD", "C22.1", "U2.36", w=0.25),
    pp("VREF", "+3V3", "C23.1", "U2.26", w=0.25),
    pp("MODE", "/weapon/U2_MODE", "R44.1", "U2.29"),
    pp("IDRIVE", "/weapon/U2_IDRIVE", "R45.1", "U2.30"),
    pp("VDS", "/weapon/U2_VDS", "R46.1", "U2.31"),
    pp("FB", "/weapon/BUCK_FB", "U2.1", "R20.2"),
    pp("FB R21", "/weapon/BUCK_FB", "R20.2", "R21.1"),
    pp("EN", "/weapon/BUCK_EN", "U2.48", "R4.2"),
    pp("EN C10", "/weapon/BUCK_EN", "C10.1", "R4.2"),
    pp("EN R5", "/weapon/BUCK_EN", "R4.2", "R5.1", margin=4.0),
    pp("EN top", "VBAT", "R4.1", "C27.1", w=0.25),
]
BLOCKS["2 U2 local"] = b2


# ---------------------------------------------------------------- block 5: U1 fan-out under its own body
# U1 (LQFP-64, bottom) has no exposed pad, so the 9.8 x 9.8 mm inside its pin ring is a free via field.  Each pin
# whose net leaves U1's immediate ring of bottom-side parts gets a straight 0.15 stub inward to a 0.4/0.2 via;
# depths step through 0.45/1.15/1.85/2.55 mm past the pad end so neighbouring vias never touch (at 0.5 pitch a
# neighbour's via can never reach a stub: 0.2 + 0.075 + 0.15 < 0.5).  The vias then carry the pin on L3 (or F).
# Pins whose only partners are bottom-side parts within 3 mm stay on the bottom (hooked up outward later).
def u1_fanout():
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


BLOCKS["5 U1 fan-out"] = u1_fanout()


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
        out.append(dict(r, retry=True, margin=7.0, via_cost=0.8, layers=[F, L3, B], layer_cost={F: 1.0, B: 1.2, L3: 1.5}))
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
    tr += [trk("/drive_right/R_VM", F, [(69.15, 28.45), (68.9, 28.7), (68.9, 29.4)], 0.4),      # C403 VM -> C400 (bottom)
           trk("/drive_right/R_VM", B, [(68.9, 29.4), (68.9, 29.9)], 0.4)]
    vi.append(via("/drive_right/R_VM", (68.9, 29.4), 0.45, 0.25))
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
          trk("/drive_right/R_VM", F, [(67.2, 31.5), (68.9, 29.8), (68.9, 29.4)], 0.7)]
    vi = [via("/drive_left/L_VM", vl, 0.6, 0.3), via("/drive_right/R_VM", vr, 0.6, 0.3)]
    return [dict(tag="VM trunks (fixed)", fixed=dict(tracks=tr, vias=vi))]


BLOCKS["6c VM trunks"] = vm_trunks()

# block 6d: VM bulk caps joined to the trunks (0.5 mm; L3 allowed where it's free)
BLOCKS["6d VM bulk"] = auto("b6d_vm_bulk", w=0.5, via=0.6, drill=0.3, layers=[F, L3, B],
                            layer_cost={F: 1.0, B: 1.0, L3: 1.3}, via_cost=1.0, margin=4.0)

# block 6: U3 / U4 local (charge pump, AVDD, buck FB/SW): short cap hookups, top first; 0.25 leaves a 0.5-pitch pin
BLOCKS["6 U3/U4 local"] = auto("b6_drives_local", w=0.25, layers=[F, B], layer_cost={F: 1.0, B: 1.5}, via_cost=2.0)

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

if __name__ == "__main__":
    upto = sys.argv[2] if len(sys.argv) > 2 else None
    out = []
    for name, reqs in BLOCKS.items():
        out += reqs
        if upto and name.startswith(upto):
            break
    json.dump(out, open(sys.argv[1], "w"), indent=0)
    print(f"{len(out)} requests")
