"""v2 block floorplan: which side each part goes on, one rectangle per block and side, and the fill of each rectangle
(sum of courtyards / rectangle area).  Renders out/floorplan.png.
    /usr/bin/python3 partdims.py --json out/partdims.json    (once, after a netlist change)
    uv run --no-project --with matplotlib python floorplan.py
Board: x 0..85 left to right, y 0..35 front (drum side) to rear, top view.  Bottom-side rectangles are given in the
same top-view coordinates."""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "gen"))
from blocknets import blk as BLOCK_OF  # noqa: E402

parts = {r["ref"]: r for r in json.load(open(HERE / "out" / "partdims.json"))}
heights = json.load(open(HERE / "out" / "heights.json"))
nets_of = {}
for r in csv.DictReader(open(MB / "design" / "netlist.csv")):
    nets_of.setdefault(r["ref"], set()).add(r["net"])

BOTTOM_MAX = 1.2    # mm: the <= ~1.1 mm bottom zone agreed with the user; Nexperia SOT-23 is 1.1 max (model 1.2)
PACK = {"BAT_IN", "PSW_S", "VBAT_SW", "PSW_G"}
HOT = {"U2", "U3", "U4", "U13", "U5", "L1", "D2", "R302", "R402", "R300", "R400", "D1", "TH1"}
# parts that must stay beside their IC on its side (DESIGN 6.13 loop-critical), or other reasons for the top
FORCE_TOP = set("C20 C21 C22 C23 C24 R44 R45 R46 C27 C28 C29 C30 C300 C301 C302 C303 C304 C305 C306 C307 C308 "
                "C400 C401 C402 C403 C404 C405 C406 C407 C408 C1 C25 C26 C31 C12 C13 C14 C18 R1 R13 R14 R32 D4 D10 "
                "R15 R20 R21 C10 R4 R5 U7 R2 R3 C2 C3 R22 R24 R26 TP10".split())
FORCE_BOTTOM = {"J1"}


def side_of(ref):
    p = parts[ref]
    if ref in FORCE_BOTTOM:
        return "B"
    if ref in FORCE_TOP or ref in HOT or p["tht"] or ref.startswith(("Q", "RS", "NT", "MH", "J")):
        return "T"
    if nets_of.get(ref, set()) & PACK:
        return "T"
    h = heights.get(p["fp"], {}).get("zmax", 0.0)
    return "T" if h > BOTTOM_MAX else "B"


# ------------------------------------------------------------------ block rectangles (x0, y0, x1, y1) per side
# key = block short name (blocknets.SHORT) + side; a block may have a rectangle on each side.
VARIANT = "A"   # A: both drives at the rear-left, sensors beside them; B: sensors at the rear-right
RECTS = {
    # ---- top
    ("PSW", "T"): (0.0, 0.0, 24.0, 13.5),
    ("BUS", "T"): (24.0, 0.0, 44.5, 16.5), ("INA", "T"): (24.0, 0.0, 44.5, 16.5),
    ("BRIDGE", "T"): (44.5, 0.0, 83.0, 18.5), ("PDIV", "T"): (44.5, 0.0, 83.0, 18.5),
    ("U3", "T"): (0.0, 13.5, 15.5, 35.0), ("VML", "T"): (0.0, 13.5, 15.5, 35.0), ("JL", "T"): (0.0, 13.5, 15.5, 35.0),
    ("U4", "T"): (15.5, 16.5, 31.0, 35.0), ("VMR", "T"): (15.5, 16.5, 31.0, 35.0), ("JR", "T"): (15.5, 16.5, 31.0, 35.0),
    ("MCU", "T"): (31.0, 18.5, 49.0, 35.0), ("LDO", "T"): (31.0, 18.5, 49.0, 35.0),
    ("U2", "T"): (49.0, 18.5, 64.0, 28.0),
    ("BUCK", "T"): (64.0, 18.5, 85.0, 28.0),
    ("BMS", "T"): (60.0, 28.0, 80.0, 35.0),
    # ---- bottom (rear band only: L4 under the front VBAT band is solid GND)
    ("MCU", "B"): (31.0, 17.0, 49.0, 35.0), ("CSAF", "B"): (31.0, 17.0, 49.0, 35.0), ("WANA", "B"): (31.0, 17.0, 49.0, 35.0),
    ("LDO", "B"): (31.0, 17.0, 49.0, 35.0), ("LED", "B"): (31.0, 17.0, 49.0, 35.0), ("INA", "B"): (31.0, 17.0, 49.0, 35.0),
    ("AND", "B"): (49.0, 18.5, 64.0, 28.0), ("WNF", "B"): (49.0, 18.5, 64.0, 28.0),
    ("J1", "B"): (62.0, 18.5, 85.0, 28.0), ("ARM", "B"): (62.0, 18.5, 85.0, 28.0),
    ("BMS", "B"): (60.0, 28.0, 80.0, 35.0),
    ("TP", "B"): (49.0, 28.0, 60.0, 35.0),
    ("U3", "B"): (0.0, 13.5, 15.5, 35.0), ("U4", "B"): (15.5, 16.5, 31.0, 35.0),
    ("DRVOFF", "B"): (15.5, 16.5, 31.0, 35.0),
}
if VARIANT == "A":
    RECTS.update({("SENL", "T"): (0.0, 13.5, 15.5, 35.0), ("SENL", "B"): (0.0, 13.5, 15.5, 35.0),
                  ("SENR", "T"): (15.5, 16.5, 31.0, 35.0), ("SENR", "B"): (15.5, 16.5, 31.0, 35.0)})
else:
    RECTS.update({("SENL", "T"): (76.0, 18.5, 85.0, 28.0), ("SENR", "T"): (76.0, 18.5, 85.0, 28.0),
                  ("SENL", "B"): (76.0, 18.5, 85.0, 28.0), ("SENR", "B"): (76.0, 18.5, 85.0, 28.0)})
# bottom keep-outs: thermal via fields under the QFN exposed pads (no bottom parts)
KEEPOUT_B = [(2.5, 18.0, 12.5, 28.0), (18.0, 19.0, 28.0, 29.0), (52.5, 20.5, 59.5, 26.5)]
REF_RECT = {"C9": (64.0, 18.5, 85.0, 28.0), "D5": (64.0, 18.5, 85.0, 28.0)}  # BMS parts beside the buck
MHS = [(x - 2.5, y - 2.5, x + 2.5, y + 2.5) for x, y in ((3, 3), (82, 3), (3, 32), (82, 32))]


def net_area(rect, side):
    """rectangle area minus the mounting-hole keep-outs (both sides)"""
    a = (rect[2] - rect[0]) * (rect[3] - rect[1])
    for m in MHS + (KEEPOUT_B if side == "B" else []):
        w = min(rect[2], m[2]) - max(rect[0], m[0])
        h = min(rect[3], m[3]) - max(rect[1], m[1])
        if w > 0 and h > 0:
            a -= w * h
    return a


def main():
    sides = {r: side_of(r) for r in parts}
    buckets = {}
    unplaced = []
    for ref, s in sides.items():
        b = BLOCK_OF.get(ref, "?")
        if ref.startswith("MH"):
            continue
        rect = REF_RECT.get(ref) or RECTS.get((b, s))
        if rect is None:
            unplaced.append((ref, b, s))
            continue
        buckets.setdefault((s, rect), []).append(ref)
    tot = {"T": 0.0, "B": 0.0}
    print(f"{'side':4s} {'rect':28s} {'area':>6s} {'parts':>6s} {'fill':>5s}  blocks")
    for (s, rect), refs in sorted(buckets.items()):
        a = net_area(rect, s)
        c = sum(parts[r]["area"] for r in refs)
        tot[s] += c
        bl = sorted({BLOCK_OF.get(r, "?") for r in refs})
        print(f"{s:4s} {str(rect):28s} {a:6.0f} {c:6.0f} {c / a:5.0%}  {','.join(bl)}")
    for s in "TB":
        print(f"side {s}: courtyards {tot[s]:.0f} mm2 (+MH on T) of 2975")
    if unplaced:
        miss = {}
        for r, b, s in unplaced:
            miss.setdefault((b, s), []).append(r)
        for (b, s), rs in sorted(miss.items()):
            print(f"NO RECTANGLE {b}/{s}: {sum(parts[r]['area'] for r in rs):.0f} mm2  {' '.join(sorted(rs))}")
    json.dump({"sides": sides, "rects": {f"{b}/{s}": v for (b, s), v in RECTS.items()}},
              open(HERE / "out" / "floorplan.json", "w"), indent=1)
    if "--png" in sys.argv:
        render(buckets)


def render(buckets):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, axs = plt.subplots(2, 1, figsize=(17, 15), dpi=80)
    for ax, s, title in ((axs[0], "T", "TOP (L1), top view"), (axs[1], "B", "BOTTOM (L4), seen from the top")):
        ax.set_xlim(-1, 86); ax.set_ylim(36, -1); ax.set_aspect("equal"); ax.set_title(title)
        ax.add_patch(Rectangle((0, 0), 85, 35, fill=False, lw=2))
        for (x, y) in ((3, 3), (82, 3), (3, 32), (82, 32)):
            ax.add_patch(Rectangle((x - 2.5, y - 2.5), 5, 5, color="#999", alpha=0.5))
        for (ss, rect), refs in buckets.items():
            if ss != s:
                continue
            a = net_area(rect, s)
            c = sum(parts[r]["area"] for r in refs)
            f = c / a
            col = "#2ca02c" if f < 0.55 else "#e0a000" if f < 0.75 else "#d62728"
            ax.add_patch(Rectangle(rect[:2], rect[2] - rect[0], rect[3] - rect[1], fill=True, color=col, alpha=0.25))
            ax.add_patch(Rectangle(rect[:2], rect[2] - rect[0], rect[3] - rect[1], fill=False, lw=1))
            bl = sorted({BLOCK_OF.get(r, "?") for r in refs})
            ax.text((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2, "\n".join(bl) + f"\n{f:.0%}", ha="center",
                    va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "out" / "floorplan.png")


if __name__ == "__main__":
    main()
