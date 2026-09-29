"""Per-part courtyard size and pad count on the v2 board, grouped by circuit block (blocks.py), with the model height.
/usr/bin/python3 partdims.py [--json out.json]   (area budget input for the floorplan)"""
import json
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gen"))
from blocks import BLOCKS  # noqa: E402

B = pcbnew.LoadBoard(str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
block_of = {r: (s, bn) for s, bl in BLOCKS.items() for bn, refs in bl.items() for r in refs}
rows = []
for f in B.GetFootprints():
    ref = f.GetReference()
    cy = f.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        bb = cy.BBox()
    else:
        bb = f.GetBoundingBox(False)
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    tht = any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads())
    rows.append(dict(ref=ref, fp=str(f.GetFPID().GetLibItemName()), w=round(w, 2), h=round(h, 2), area=round(w * h, 1),
                     pads=f.GetPadCount(), tht=tht, sheet=block_of.get(ref, ("?", "?"))[0],
                     block=block_of.get(ref, ("?", "?"))[1]))
if "--json" in sys.argv:
    json.dump(rows, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
tot = {}
for r in rows:
    tot.setdefault((r["sheet"], r["block"]), []).append(r)
grand = 0
for (s, bn), rs in sorted(tot.items()):
    a = sum(r["area"] for r in rs)
    grand += a
    big = sorted(rs, key=lambda r: -r["area"])[:4]
    print(f"{s:11s} {bn:45s} n={len(rs):3d} {a:7.1f} mm2   " + ", ".join(f"{r['ref']} {r['w']}x{r['h']}" for r in big))
print(f"total courtyard {grand:.0f} mm2 of {85 * 35} per side ({2 * 85 * 35} both)")
