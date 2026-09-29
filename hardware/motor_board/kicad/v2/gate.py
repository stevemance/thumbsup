"""One routability-gate run: place (spec.py) -> dump -> MCU pin co-assignment on the real pads -> global route.
    python3 gate.py [--iters N] [--tag name]
Needs /usr/bin/python3 (pcbnew) and uv.  Prints the placer problems, the pin solve status and the router summary;
keeps out/gate_<tag>.txt, out/groute.png."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = sys.argv[1:]
iters = args[args.index("--iters") + 1] if "--iters" in args else "10"
tag = args[args.index("--tag") + 1] if "--tag" in args else "run"
log = []


def run(cmd, keep=lambda l: True):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    out = [l for l in (r.stdout + r.stderr).splitlines() if "assert" not in l and keep(l)]
    log.extend(out)
    print("\n".join(out), flush=True)
    return out


run(["/usr/bin/python3", "place.py"], lambda l: l.startswith(("board", "PROBLEM")))
run(["/usr/bin/python3", "render.py", "dump"])
mcu = [l for l in open(HERE / "spec.py") if l.strip().startswith('"U1":')][0]
x, y, rot = [v.strip() for v in mcu.split("(")[1].split(",")[:3]]
run(["uv", "run", "--no-project", "--with", "ortools", "python", "pinsolve.py", x, y, rot, "--geom", "out/geom_place.json"],
    lambda l: l.startswith(("status", "drive timers")))
run(["uv", "run", "--no-project", "--with", "numpy", "--with", "matplotlib", "python", "groute.py",
     "--pins", f"out/pinsolve_{int(float(rot))}.json", "--iters", iters], lambda l: l.startswith(("best", "nets")))
(HERE / "out" / f"gate_{tag}.txt").write_text("\n".join(log) + "\n")
