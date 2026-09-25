"""Rebuild the routed board: base snapshot -> router (all blocks up to N) -> apply -> DRC summary.
/usr/bin/python3 route_all.py [block-prefix]      (close KiCad first; writes kicad/motor_board/motor_board.kicad_pcb)"""
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "motor_board"
PCB, PRO = PROJ / "motor_board.kicad_pcb", PROJ / "motor_board.kicad_pro"
BASE = HERE / "base" / "motor_board_base.kicad_pcb"
W = HERE / "out" / "route"
W.mkdir(parents=True, exist_ok=True)
upto = sys.argv[1] if len(sys.argv) > 1 else ""


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "property.h" not in l and "memory leak" not in l)
    if r.returncode:
        raise SystemExit(out)
    return out


pro = PRO.read_text()
print(run(["/usr/bin/python3", str(HERE / "geom_export.py"), str(BASE), str(W / "geom.json")]))
print(run(["python3", str(HERE / "route_blocks.py"), str(W / "blocks.json"), upto]))
print(run(["uv", "run", "--no-project", "--with", "numpy", "--with", "scipy", "--with", "matplotlib", "python",
           str(HERE / "router.py"), str(W / "geom.json"), str(W / "blocks.json"), str(W / "routes.json")], timeout=7200))
print(run(["/usr/bin/python3", str(HERE / "apply_routes.py"), str(BASE), str(W / "routes.json"), str(PCB)]))
PRO.write_text(pro)
subprocess.run(["kicad-cli", "pcb", "drc", "--schematic-parity", "--format", "json", "-o", str(W / "drc.json"), str(PCB)],
               capture_output=True)
r = json.loads((W / "drc.json").read_text())
err = Counter(v["type"] for v in r["violations"] if v["severity"] == "error")
print("DRC errors:", dict(err) or 0, "| unconnected:", len(r["unconnected_items"]), "| parity:", len(r.get("schematic_parity", [])))
for v in r["violations"]:
    if v["severity"] == "error":
        print("   ", v["type"], "|", " / ".join(i["description"][:70] for i in v["items"]))
