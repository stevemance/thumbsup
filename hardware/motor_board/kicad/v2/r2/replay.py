"""Replay another board's copper for chosen nets as tail edits (explicit tracks + vias), so a hand stage can keep a
router result for the nets it did not change.  Reads a view.py dump (board-local mm).
    python3 r2/replay.py <dump.json> <net,net,...> > out.json      (JSON list of edits: track / via ops)
Duplicate segments (the router's back-and-forth stubs) are dropped."""
import json
import sys

D = json.load(open(sys.argv[1]))
want = set(sys.argv[2].split(","))
LAY = {"F": "F.Cu", "L3": "In2.Cu", "B": "B.Cu"}


def nm(n):
    return n.split("/")[-1]


out, seen = [], set()
if len(sys.argv) > 3:                      # a base dump: its copper is already on the target board, skip it
    B = json.load(open(sys.argv[3]))
    for t in B["tracks"]:
        a, b = tuple(round(v, 4) for v in t["a"]), tuple(round(v, 4) for v in t["b"])
        seen.add((t["net"], t["layer"], min(a, b), max(a, b)))
    skipv = {(v["net"], tuple(round(x, 4) for x in v["c"])) for v in B["vias"]}
else:
    skipv = set()
for t in D["tracks"]:
    if nm(t["net"]) not in want or t["layer"] not in LAY:
        continue
    a, b = tuple(round(v, 4) for v in t["a"]), tuple(round(v, 4) for v in t["b"])
    if a == b:
        continue
    k = (t["net"], t["layer"], min(a, b), max(a, b))
    if k in seen:
        continue
    seen.add(k)
    out.append(dict(op="track", net=t["net"], layer=LAY[t["layer"]], pts=[a, b], w=t["w"]))
for v in D["vias"]:
    if nm(v["net"]) in want and (v["net"], tuple(round(x, 4) for x in v["c"])) not in skipv:
        out.append(dict(op="via", net=v["net"], c=tuple(round(x, 4) for x in v["c"]), d=v["d"], drill=v["drill"]))
json.dump(out, sys.stdout)
print(f"{len(out)} edits", file=sys.stderr)
