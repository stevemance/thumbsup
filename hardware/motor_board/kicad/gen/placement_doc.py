"""Write ../../PLACEMENT.md: the prose (PROSE below) + a per-part table generated from out/placement_v2.csv
(which place_v2.py writes from the board and the spec), so the table always matches the board."""
import csv
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parents[1] / "PLACEMENT.md"
rows = list(csv.DictReader(open(HERE / "out" / "placement_v2.csv")))
spec = (HERE / "placement_spec.py").read_text()
bw = re.search(r"BW, BH = ([\d.]+), ([\d.]+)", spec)
BW, BH = float(bw.group(1)), float(bw.group(2))

GROUPS = [
    ("Weapon bridge", r"^(Q[1-6]|RS[1-3]|C25|C26|C31|JW\d|NT\d|TH1)$"),
    ("Battery entry and power switch", r"^(JBAT\d|Q7|Q8|U13|C12|C13|C14|C18|R1|R13|R14|R32|D4|D10|RS4|D1|C1|R15)$"),
    ("Pack monitor (INA239)", r"^(U7|R2|R3|C2|C3|R12)$"),
    ("Cell monitor (BQ76907)", r"^(U8|J4|R6|R7|R8|R9|R10|R11|C4|C5|C6|C7|C8|C9|C11|D5)$"),
    ("Weapon driver and 5 V buck", r"^(U2|C2[0-4]|C27|C28|C29|C30|R4|R5|C10|R20|R21|R44|R45|R46|L1|D2)$"),
    ("Drive left", r"^(U3|C30\d|C310|R30[0-2]|JL\d)$"),
    ("Drive right", r"^(U4|C40\d|C410|R40[0-2]|JR\d|R50|TP8)$"),
    ("MCU, LDO and header", r"^(U1|U5|C6\d|C7[0-1]|C74|R6[0-4]|C8\d|C9\d|R7\d|R8\d|R16|R17|R33|R40|J1|C41|C42|C43|C44|R23|R25|R27|R43|R42|C19|C68|C69|C70|D3)$"),
    ("Phase dividers", r"^(R22|R24|R26)$"),
    ("Weapon interlock and ARM", r"^(U6|U14|C40|C15|C16|C17|R18|R19|R41|R47|R48|R49|D9)$"),
    ("Sensor channels", r"^(J2|J3|U9|U10|U11|U12|JP\d|D7|D8|R5[2-9]|R11[0-7]|C4[5-9]|C50|C7[23]|C11[0-6])$"),
    ("Test pads", r"^TP\d+$"),
    ("Mounting", r"^MH\d$"),
]


def group(ref):
    for g, pat in GROUPS:
        if re.match(pat, ref):
            return g
    return "Other"


table = {}
for r in rows:
    table.setdefault(group(r["ref"]), []).append(r)



def md_table(rs):
    lines = ["| Ref | Value | Side | x, y (mm) | Rot | Why it is here | Measured |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        meas = f"{float(r['anchor_mm']):.1f} mm to {r['rule'][5:]}" if r["anchor_mm"] else "placed explicitly"
        lines.append(f"| {r['ref']} | {r['value']} | {r['side']} | {float(r['x']):.2f}, {float(r['y']):.2f} | {r['rot']} | {r['why']} | {meas} |")
    return "\n".join(lines)


prose = (HERE / "placement_prose.md").read_text().format(BW=BW, BH=BH, AREA=round(BW * BH))
crit = subprocess.run(["/usr/bin/python3", str(HERE / "critical.py")], capture_output=True, text=True).stdout
parts = [prose, "\n## Per-part placement\n",
         "Coordinates are the footprint origin, board top view, origin at the front-left corner, y toward the rear. "
         "\"Measured\" is the distance from the part's nearest pad to the pad (or point) it was placed against.\n"]
for g, _ in GROUPS + [("Other", "")]:
    if g in table:
        parts += [f"\n### {g}\n", md_table(sorted(table[g], key=lambda r: (re.sub(r'\d', '', r['ref']), int(re.sub(r'\D', '', r['ref']) or 0))))]
parts += ["\n## Critical distances (kicad/gen/critical.py)\n", "```", crit.strip(), "```\n"]
DOC.write_text("\n".join(parts) + "\n")
print("wrote", DOC, len(rows), "parts")
