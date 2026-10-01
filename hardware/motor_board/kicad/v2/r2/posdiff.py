"""compare footprint poses of two boards: /usr/bin/python3 r2/posdiff.py a.kicad_pcb b.kicad_pcb"""
import sys

import pcbnew


def poses(f):
    b = pcbnew.LoadBoard(f)
    t = pcbnew.ToMM
    return {fp.GetReference(): (round(t(fp.GetPosition().x) - 100, 3), round(t(fp.GetPosition().y) - 70, 3),
            round(fp.GetOrientationDegrees()), "B" if fp.IsFlipped() else "T") for fp in b.GetFootprints()}


a, b = poses(sys.argv[1]), poses(sys.argv[2])
for r in sorted(a):
    if a[r] != b.get(r):
        print(r, a[r], "->", b.get(r))
