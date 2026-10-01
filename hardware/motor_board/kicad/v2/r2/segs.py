"""segs.py <dump.json> x0 y0 x1 y1 [layers F,L3,B] [nets substr,...] : tracks (net layer a b w) and vias in a box,
merged into polylines per net/layer where segments chain"""
import json
import sys

D = json.load(open(sys.argv[1]))
x0, y0, x1, y1 = map(float, sys.argv[2:6])
lays = set(sys.argv[6].split(",")) if len(sys.argv) > 6 and sys.argv[6] else {"F", "L3", "B"}
nf = sys.argv[7].split(",") if len(sys.argv) > 7 else None


def ins(p, m=0.0):
    return x0 - m <= p[0] <= x1 + m and y0 - m <= p[1] <= y1 + m


def seg_in(a, b):
    return any(ins((a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20)) for k in range(21))


def nm(n):
    return n.split("/")[-1]


rows = {}
for t in D["tracks"]:
    if t["layer"] not in lays or not seg_in(t["a"], t["b"]):
        continue
    if nf and not any(s in nm(t["net"]) for s in nf):
        continue
    rows.setdefault((nm(t["net"]), t["layer"], t["w"]), []).append((tuple(t["a"]), tuple(t["b"])))
for (n, ly, w), segs in sorted(rows.items()):
    # chain into polylines
    segs = [list(s) for s in segs]
    lines = []
    while segs:
        a, b = segs.pop()
        line = [a, b]
        grown = True
        while grown:
            grown = False
            for s in segs:
                if s[0] == line[-1]:
                    line.append(s[1]); segs.remove(s); grown = True; break
                if s[1] == line[-1]:
                    line.append(s[0]); segs.remove(s); grown = True; break
                if s[1] == line[0]:
                    line.insert(0, s[0]); segs.remove(s); grown = True; break
                if s[0] == line[0]:
                    line.insert(0, s[1]); segs.remove(s); grown = True; break
        lines.append(line)
    for l in lines:
        print(f"{n:12s} {ly:2s} w{w:.2f} " + " ".join(f"({p[0]:.2f},{p[1]:.2f})" for p in l))
for v in D["vias"]:
    if ins(v["c"]) and (not nf or any(s in nm(v["net"]) for s in nf)):
        print(f"{nm(v['net']):12s} via ({v['c'][0]:.2f},{v['c'][1]:.2f}) d{v['d']}")
