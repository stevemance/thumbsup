"""Courtyard size (rot 0), pad bbox, THT flag and footprint of every part on the board -> out/partdims.json."""
import json
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
b = pcbnew.LoadBoard(str(HERE.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
out = {}
for fp in b.GetFootprints():
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(0)
    fp.BuildCourtyardCaches()
    c = fp.GetCourtyard(pcbnew.F_CrtYd)
    pads = list(fp.Pads())
    xs = [t(p.GetBoundingBox().GetLeft()) for p in pads] + [t(p.GetBoundingBox().GetRight()) for p in pads]
    ys = [t(p.GetBoundingBox().GetTop()) for p in pads] + [t(p.GetBoundingBox().GetBottom()) for p in pads]
    pw, ph = max(xs) - min(xs), max(ys) - min(ys)
    if c.OutlineCount():
        bb = c.BBox(); w, h = t(bb.GetWidth()), t(bb.GetHeight())
    else:
        w, h = pw + 0.5, ph + 0.5
    out[fp.GetReference()] = dict(fp=fp.GetFPIDAsString(), w=round(w, 2), h=round(h, 2), pad_w=round(pw, 2), pad_h=round(ph, 2),
                                  tht=any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in pads),
                                  value=fp.GetValue())
(HERE / "out" / "partdims.json").write_text(json.dumps(out, indent=1, sort_keys=True))
print(len(out))
