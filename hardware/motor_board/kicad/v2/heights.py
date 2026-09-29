"""Model height (max z of the STEP) per footprint on the v2 board -> out/heights.json.
Two steps: `/usr/bin/python3 heights.py list` writes out/models.json (footprint -> model path) with pcbnew, then
`uv run --no-project --with build123d python heights.py measure` reads each STEP and writes out/heights.json."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
PROJ = HERE.parent / "motor_board"
ENV = {"${KIPRJMOD}": str(PROJ), "${KICAD10_3DMODEL_DIR}": "/usr/share/kicad/3dmodels"}

if sys.argv[1] == "list":
    import pcbnew
    b = pcbnew.LoadBoard(str(PROJ / "motor_board.kicad_pcb"))
    m = {}
    for f in b.GetFootprints():
        name = str(f.GetFPID().GetLibItemName())
        ms = list(f.Models())
        if ms:
            p = ms[0].m_Filename
            for k, v in ENV.items():
                p = p.replace(k, v)
            if p.endswith(".wrl"):
                p = p[:-4] + ".step"
            m[name] = dict(path=p, offz=pcbnew.ToMM(0) + ms[0].m_Offset.z, sz=ms[0].m_Scale.z)
    json.dump(m, open(OUT / "models.json", "w"), indent=1)
    print(len(m), "footprints with models")
else:
    from build123d import import_step
    m = json.load(open(OUT / "models.json"))
    h = {}
    for name, d in sorted(m.items()):
        try:
            bb = import_step(d["path"]).bounding_box()
            h[name] = dict(zmax=round(bb.max.Z + d["offz"], 2), zmin=round(bb.min.Z + d["offz"], 2))
        except Exception as e:  # noqa: BLE001
            h[name] = dict(error=str(e)[:80])
        print(f"{name:60s} {h[name]}")
    json.dump(h, open(OUT / "heights.json", "w"), indent=1)
