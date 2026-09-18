"""Logic routing with Freerouting: export the board as Specctra DSN, run the
headless router, import the session, refill zones.

    /usr/bin/python3 tools/pcb/route.py [passes]

Hand copper from copper.py (zones, via fields, gate/Kelvin stubs) is exported with the
board; zones become planes Freerouting connects to with vias, tracks are re-imported
with the session."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FREEROUTING = ROOT / "hardware" / "tools" / "freerouting" / "freerouting-2.4.1-linux-x64" / "bin" / "freerouting"


def autoroute(pcb: Path, passes: int = 30, work: Path | None = None) -> Path:
    work = work or pcb.parent
    dsn, ses = work / (pcb.stem + ".dsn"), work / (pcb.stem + ".ses")
    export_dsn(pcb, dsn)
    board = pcbnew.LoadBoard(str(pcb))
    ses.unlink(missing_ok=True)
    env = dict(os.environ, FREEROUTING__GUI__ENABLED="false")
    # fanout (escape vias on every SMD pad) is useless on this board and eats 20 passes; the
    # autorouter fans out on its own.  Optimizer passes are capped so a run stays < 1 h.
    cmd = [str(FREEROUTING), "-de", str(dsn), "-do", str(ses), "-mp", str(passes), "-mt", "6",
           "--gui.enabled=false", "--router.fanout.enabled=false", f"--router.max_passes={passes}",
           "--router.optimizer.enabled=false"]      # the session is written right after the passes
    print(" ".join(cmd))
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-12:])
    print(tail)
    if not ses.exists():
        raise SystemExit("Freerouting produced no session file")
    import_session(pcb, ses, board)
    return ses


def export_dsn(pcb: Path, dsn: Path):
    """Specctra export with the bottom GND pour left out: exported as a plane it makes every
    bottom GND pad look connected, so Freerouting ignores GND and its tracks then carve the
    pour into islands that strand pads.  Without it the router joins each GND pad to the
    nearest GND via / pad; KiCad refills the pour around those tracks on import."""
    board = pcbnew.LoadBoard(str(pcb))
    for z in list(board.Zones()):
        if z.GetZoneName() == "GND bottom":
            board.Remove(z)
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise SystemExit("DSN export failed")
    # do not save this board object (removing zones from Python corrupts the wrapper on save)


def import_session(pcb: Path, ses: Path, board=None):
    board = board or pcbnew.LoadBoard(str(pcb))
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise SystemExit("SES import failed")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    import copper  # noqa: E402

    import json as _json
    from board import ROOT as _ROOT
    outline = _json.loads((_ROOT / "hardware" / "mech" / "board_outline.json").read_text())["outline"]
    # (keep-out vias are avoided at build time; relocating here broke the SWIG board proxy)
    n, miss = copper.stitch_stranded_pads(board, outline)
    print(f"GND vias for stranded bottom pads after routing: {n} placed, {len(miss)} without a spot {miss[:12]}")
    print("GND island stitch vias after routing (added, missed):", copper.stitch_gnd_islands(board, outline))
    pcbnew.SaveBoard(str(pcb), board)


def stats(pcb: Path):
    """kicad-cli DRC: violation counts and the unconnected nets, most-frequent first."""
    import json
    from collections import Counter

    rep = pcb.with_suffix(".drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "-o", str(rep), str(pcb)], capture_output=True)
    r = json.loads(rep.read_text())
    c = Counter(v["type"] for v in r.get("violations", []))
    unc = r.get("unconnected_items", [])
    nets = Counter()
    for u in unc:
        for it in u.get("items", []):
            d = it.get("description", "")
            if "[" in d:
                nets[d.split("[")[1].split("]")[0]] += 1
                break
    print("DRC:", dict(c) if c else "clean", "| unconnected:", len(unc))
    for net, n in nets.most_common(40):
        print(f"  {n:3d}  {net}")
    return len(unc), c


if __name__ == "__main__":
    from board import KICAD  # noqa: E402

    if len(sys.argv) > 2 and sys.argv[1] == "export":      # route.py export <pcb> <dsn>
        export_dsn(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) > 2 and sys.argv[1] == "import":    # route.py import <pcb> <ses>
        import_session(Path(sys.argv[2]), Path(sys.argv[3]))
        stats(Path(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats(Path(sys.argv[2]))
    else:
        autoroute(KICAD / "thumbsup.kicad_pcb", int(sys.argv[1]) if len(sys.argv) > 1 else 40)
