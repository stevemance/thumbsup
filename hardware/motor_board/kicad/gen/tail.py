"""Freeze-and-edit loop for the routing tail.

    /usr/bin/python3 tail.py            apply tail_edits.EDITS to frozen/board.kicad_pcb -> the project board, DRC
    /usr/bin/python3 tail.py --no-drc   (skip DRC: geometry only)
    /usr/bin/python3 tail.py freeze     make the current project board the new frozen snapshot (after a good run)

The frozen board is a full build of route_all.py (every part and track as it was); tail_edits.py lists the edits
made on top of it, in order, the way one edits a board in KiCad:

    dict(op="move", ref="C112", x=34.9, y=27.0, rot=90, side="F")     footprint centre / rotation / side
    dict(op="rip", box=(x0, y0, x1, y1), nets=[...], layers=[...])    delete tracks with an end in the box, vias in it
    dict(op="rip_ref", ref="R71")                                      delete the stubs on a part's pads (before a move)
    dict(op="track", net=..., layer="F.Cu", pts=[...], w=0.15)
    dict(op="via", net=..., c=(x, y), d=0.4, drill=0.2)
    dict(op="route", net=..., a=("pad", "U9", "7"), b=("via", 32.0, 27.05), layers=[...], ...)   grid router
    dict(op="drop", pad=("C111", "2"), net="GND")                     pad -> nearest legal via (e.g. to a GND plane)

All route/drop requests run in one router pass after the board edits, on the edited board.  Coordinates are
board-local mm (as everywhere in gen/)."""
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB, PRO = PROJ / "motor_board.kicad_pcb", PROJ / "motor_board.kicad_pro"
FROZEN = HERE / "frozen" / "board.kicad_pcb"
W = HERE / "out" / "tail"
EXP = __import__("os").environ.get("TAIL_EXP")      # experiment: edits from <EXP>.py, own work dir and board copy
if EXP:
    W = HERE / "out" / "exp" / EXP
    (W / "proj").mkdir(parents=True, exist_ok=True)
    shutil.copy(PRO, W / "proj" / PRO.name)
    PCB, PRO = W / "proj" / PCB.name, W / "proj" / PRO.name
W.mkdir(parents=True, exist_ok=True)
T0 = time.time()


def lap(what):
    print(f"[{time.time() - T0:6.1f} s] {what}")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines()
                    if "property.h" not in l and "memory leak" not in l and "Debug:" not in l)
    if r.returncode:
        raise SystemExit(out)
    return out


if len(sys.argv) > 1 and sys.argv[1] == "freeze":
    shutil.copy(PCB, FROZEN)
    print("frozen:", FROZEN)
    sys.exit(0)

pro = PRO.read_text()
work = W / "work.kicad_pcb"
# 1. board edits (pcbnew, own process)
BASE = __import__("os").environ.get("TAIL_BASE") or str(FROZEN)   # experiment on another board (multi-stage edits)
print(run(["/usr/bin/python3", str(HERE / "tail_apply.py"), BASE, str(work), str(W / "requests.json")] + ([EXP] if EXP else [])))
lap("board edits")
reqs = json.load(open(W / "requests.json"))
if reqs:
    print(run(["/usr/bin/python3", str(HERE / "geom_export.py"), str(work), str(W / "geom.json")]))
    lap("geometry export")
    out = run(["uv", "run", "--no-project", "--with", "numpy", "--with", "scipy", "--with", "matplotlib", "python",
               str(HERE / "router.py"), str(W / "geom.json"), str(W / "requests.json"), str(W / "routes.json")],
              timeout=3600, env=dict(__import__("os").environ, RRR=__import__("os").environ.get("TAIL_RRR", "0")))
    print("\n".join(l for l in out.splitlines() if l.startswith(("ok", "FAIL"))))
    lap("router")
    routes = json.load(open(W / "routes.json"))
    why = [r_ for r_ in routes if r_["tag"].startswith("why ")]
    if why:                            # report the existing tracks each free path runs into; never apply probes
        import math
        g = json.load(open(W / "geom.json"))

        def sd(a, b_, p):
            dx, dy = b_[0] - a[0], b_[1] - a[1]
            L2 = dx * dx + dy * dy
            u = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)

        def crosses(p, q, r, s_):
            def o(a, b_, c):
                return (b_[0] - a[0]) * (c[1] - a[1]) - (b_[1] - a[1]) * (c[0] - a[0])
            return o(p, q, r) * o(p, q, s_) < 0 and o(r, s_, p) * o(r, s_, q) < 0

        for r_ in why:
            if not r_["ok"]:
                print(r_["tag"], "-> no path even ignoring tracks (pads / vias / keep-outs block it)")
                continue
            hits = {}
            for tt in r_["tracks"]:
                pts = tt["pts"]
                for e_ in g["tracks"]:
                    if e_["layer"] != tt["layer"] or e_["net"] == tt["net"]:
                        continue
                    for a, b_ in zip(pts, pts[1:]):
                        dmin = 0 if crosses(a, b_, e_["a"], e_["b"]) else \
                            min(sd(a, b_, e_["a"]), sd(a, b_, e_["b"]), sd(e_["a"], e_["b"], a), sd(e_["a"], e_["b"], b_))
                        if dmin < (tt["w"] + e_["w"]) / 2 + 0.15:
                            hits.setdefault((e_["net"], e_["layer"]), []).append(tuple(round(c, 2) for c in e_["a"]))
                            break
            print(r_["tag"], f"-> free path {r_['length']} mm on {sorted({t_['layer'] for t_ in r_['tracks']})}; crosses:")
            for (n_, l_), where in sorted(hits.items()):
                print(f"      {n_:24s} {l_:7s} near {where[:3]}")
        json.dump(why, open(W / "why.json", "w"))
        json.dump([r_ for r_ in routes if not r_["tag"].startswith("why ")], open(W / "routes.json", "w"))
    print(run(["/usr/bin/python3", str(HERE / "apply_routes.py"), str(work), str(W / "routes.json"), str(PCB)]))
else:
    run(["/usr/bin/python3", "-c", f"import pcbnew; b = pcbnew.LoadBoard('{work}'); "
         f"pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard('{PCB}', b)"])
PRO.write_text(pro)
lap("applied + zones filled")
if "--no-drc" in sys.argv:
    sys.exit(0)
subprocess.run(["kicad-cli", "pcb", "drc"] + ([] if EXP else ["--schematic-parity"]) + [ "--format", "json", "-o", str(W / "drc.json"), str(PCB)],
               capture_output=True)
r = json.loads((W / "drc.json").read_text())
err = Counter(v["type"] for v in r["violations"] if v["severity"] == "error")
print("DRC errors:", dict(err) or 0, "| unconnected:", len(r["unconnected_items"]), "| parity:", len(r.get("schematic_parity", [])))
for v in r["violations"]:
    if v["severity"] == "error":
        print("   ", v["type"], "|", " / ".join(i["description"][:70] for i in v["items"]))
lap("DRC")
