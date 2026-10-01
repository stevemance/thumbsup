"""Remaining opens of a DRC json with both end coordinates (board mm):  python3 r2/openlist.py <drc.json> [GND]"""
import json
import re
import sys

d = json.load(open(sys.argv[1]))
want_gnd = len(sys.argv) > 2
for u in d["unconnected_items"]:
    m = re.search(r"\[([^\]]+)\]", u["items"][0]["description"])
    n = m.group(1).split("/")[-1] if m else "?"
    if (n == "GND") != want_gnd:
        continue
    ends = []
    for i in u["items"]:
        desc = re.sub(r" on .*", "", i["description"])
        desc = re.sub(r"\[[^\]]*\] ", "", desc)
        ends.append(f"{desc[:26]} ({i['pos']['x'] - 100:.2f}, {i['pos']['y'] - 70:.2f})")
    print(f"{n:11s} " + "  <->  ".join(ends))
