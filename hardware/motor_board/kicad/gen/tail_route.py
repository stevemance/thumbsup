"""Tail routing with Freerouting: route only what the planned blocks + grid router left open.

    /usr/bin/python3 tail_route.py export     # built board -> out/tail/board.dsn (all existing copper locked)
    /usr/bin/python3 tail_route.py run [passes]
    /usr/bin/python3 tail_route.py import     # session -> pairs/tail_fr.json (new copper only, as a fixed block)

Everything already on the board is exported locked ("protect"), so Freerouting cannot move it.  The two GND
layers are exported as power planes (no signal tracks there), the outer GND fills are left out (as planes they
would make every GND pad look connected).  Only the copper Freerouting adds comes back, as fixed geometry that
route_blocks.py replays after the grid-router blocks: the pipeline stays one reproducible build."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PCB = HERE.parent / "motor_board" / "motor_board.kicad_pcb"
OUT = HERE / "out" / "tail"
OUT.mkdir(parents=True, exist_ok=True)
DSN, SES = OUT / "board.dsn", OUT / "board.ses"
FR = Path(os.environ.get("FREEROUTING", "/home/smance/projects/thumbsup/hardware/tools/freerouting/freerouting-2.4.1-linux-x64/bin/freerouting"))   # untracked install
LAYER = {pcbnew.F_Cu: "F.Cu", pcbnew.In2_Cu: "In2.Cu", pcbnew.In3_Cu: "In3.Cu", pcbnew.B_Cu: "B.Cu"}


def key_t(t):
    a, b = t.GetStart(), t.GetEnd()
    return ("t", t.GetLayer(), t.GetNetname(), tuple(sorted([(a.x, a.y), (b.x, b.y)])))


def key_v(v):
    p = v.GetPosition()
    return ("v", v.GetNetname(), p.x, p.y)


def export():
    b = pcbnew.LoadBoard(str(PCB))
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    b.SetLayerType(pcbnew.In4_Cu, pcbnew.LT_POWER)
    for x in b.GetTracks():
        x.SetLocked(True)
    before = [key_t(x) if x.GetClass() == "PCB_TRACK" else key_v(x) for x in b.GetTracks()
              if x.GetClass() in ("PCB_TRACK", "PCB_VIA")]
    json.dump([list(map(lambda e: list(e) if isinstance(e, tuple) else e, k)) for k in before],
              open(OUT / "before.json", "w"))
    for z in list(b.Zones()):
        if z.GetZoneName().endswith("GND fill"):
            b.Remove(z)
    if not pcbnew.ExportSpecctraDSN(b, str(DSN)):
        raise SystemExit("DSN export failed")
    # the tail runs through gaps sized for 0.2 mm: the net classes' 0.25-0.5 mm widths (rails, power, gates) would be
    # forced into them and fail; clearances stay as they are
    import re
    txt = DSN.read_text()
    txt = re.sub(r"\(width (250|400|500)\)", "(width 200)", txt)
    DSN.write_text(txt)
    print("exported", DSN, len(before), "existing items")


def run(passes=20):
    SES.unlink(missing_ok=True)
    env = dict(os.environ, FREEROUTING__GUI__ENABLED="false")
    cmd = [str(FR), "-de", str(DSN), "-do", str(SES), "-mp", str(passes), "-mt", "6", "--gui.enabled=false",
           "--router.fanout.enabled=false", f"--router.max_passes={passes}", "--router.optimizer.enabled=false"]
    print(" ".join(cmd))
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=5400)
    print("\n".join((p.stdout + p.stderr).splitlines()[-15:]))
    print("session:", SES.exists())


def norm(k):
    return json.dumps(k)


def imp():
    b = pcbnew.LoadBoard(str(PCB))
    if not pcbnew.ImportSpecctraSES(b, str(SES)):
        raise SystemExit("SES import failed")
    before = {norm(k) for k in json.load(open(OUT / "before.json"))}
    bb = b.GetBoardEdgesBoundingBox()
    t = pcbnew.ToMM
    ox, oy = t(bb.GetLeft()) + 0.05, t(bb.GetTop()) + 0.05
    tracks, vias = [], []
    for x in b.GetTracks():
        if x.GetClass() == "PCB_TRACK":
            k = key_t(x)
            if norm([list(e) if isinstance(e, tuple) else e for e in k]) in before:
                continue
            if x.GetLayer() not in LAYER:
                print("skipped track on", b.GetLayerName(x.GetLayer()))
                continue
            a, c = x.GetStart(), x.GetEnd()
            tracks.append(dict(net=x.GetNetname(), layer=LAYER[x.GetLayer()], w=round(t(x.GetWidth()), 3),
                               pts=[[round(t(a.x) - ox, 4), round(t(a.y) - oy, 4)], [round(t(c.x) - ox, 4), round(t(c.y) - oy, 4)]]))
        elif x.GetClass() == "PCB_VIA":
            k = key_v(x)
            if norm(list(k)) in before:
                continue
            p = x.GetPosition()
            vias.append(dict(net=x.GetNetname(), c=[round(t(p.x) - ox, 4), round(t(p.y) - oy, 4)],
                             d=round(t(x.GetWidth(pcbnew.F_Cu)), 3), drill=round(t(x.GetDrillValue()), 3)))
    json.dump(dict(tracks=tracks, vias=vias), open(HERE / "pairs" / "tail_fr.json", "w"), indent=0)
    nets = sorted({x["net"] for x in tracks + [dict(net=v["net"]) for v in vias]})
    print(f"new copper: {len(tracks)} track segments, {len(vias)} vias on {len(nets)} nets")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export":
        export()
    elif cmd == "run":
        run(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "import":
        imp()
