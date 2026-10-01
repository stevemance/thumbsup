import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); t = pcbnew.ToMM
for f in b.GetFootprints():
    if f.GetReference() in sys.argv[2:]:
        print(f.GetReference(), round(t(f.GetPosition().x) - 100, 3), round(t(f.GetPosition().y) - 70, 3), round(f.GetOrientationDegrees()), "B" if f.IsFlipped() else "T")
