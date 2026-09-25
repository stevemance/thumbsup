"""Distances for the placement-critical pairs: each part's pad on the shared net to the IC pin it serves
(centre distance and pad-edge gap, mm; 'via' = the two are on opposite sides).  Run with /usr/bin/python3."""
import math
from pathlib import Path

import pcbnew

b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent.parent / "motor_board" / "motor_board.kicad_pcb"))
t = pcbnew.ToMM
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}

# (part, IC, pin, limit mm or None, rule)
PAIRS = [
    ("C24", "U2", "6", 2.0, "U2 VM 100 nF 'as close as possible' (DRV8323 p73)"),
    ("C21", "U2", "5", 2.5, "VCP cap at the pin"), ("C20", "U2", "4", 2.5, "CP flying cap at the pins"),
    ("C22", "U2", "36", 2.5, "DVDD cap"), ("C23", "U2", "26", 2.5, "VREF cap"),
    ("R44", "U2", "29", 2.0, "strap within 2 mm (DESIGN 6.4)"), ("R45", "U2", "30", 2.0, "strap within 2 mm"),
    ("R46", "U2", "31", 2.0, "strap within 2 mm"),
    ("C27", "U2", "47", 3.0, "buck VIN cap first (LMR16006)"), ("C28", "U2", "44", 3.0, "bootstrap cap"),
    ("L1", "U2", "45", 3.0, "SW node tiny"), ("D2", "L1", "1", 2.0, "D2 cathode at L1 SW"),
    ("C29", "D2", "2", 2.0, "output cap GND at D2 anode"), ("C30", "L1", "2", 2.0, "output cap at L1 +5V"),
    ("R20", "U2", "1", 3.0, "FB divider at pin 1"),
    ("C300", "U3", "9", 2.0, "VM 100 nF within 2 mm (DESIGN 6.6)"), ("C301", "U3", "11", 2.0, "VM 100 nF within 2 mm"),
    ("C303", "U3", "8", 2.5, "CP cap"), ("C304", "U3", "7", 2.5, "CPH/CPL cap"), ("C305", "U3", "25", 2.5, "AVDD cap"),
    ("C306", "U3", "37", 2.5, "VREF cap"),
    ("C400", "U4", "9", 2.0, "VM 100 nF within 2 mm"), ("C401", "U4", "11", 2.0, "VM 100 nF within 2 mm"),
    ("C403", "U4", "8", 2.5, "CP cap"), ("C404", "U4", "7", 2.5, "CPH/CPL cap"), ("C405", "U4", "25", 2.5, "AVDD cap"),
    ("C406", "U4", "37", 2.5, "VREF cap"),
    ("C302", "U3", "10", 4.0, "VM 10 uF (bottom, via)"), ("C308", "U3", "10", 4.0, ""), ("C309", "U3", "10", 4.0, ""), ("C310", "U3", "10", 4.0, ""),
    ("C402", "U4", "10", 4.0, "VM 10 uF (bottom, via)"), ("C408", "U4", "10", 4.0, ""), ("C409", "U4", "10", 4.0, ""), ("C410", "U4", "10", 4.0, ""),
    ("C60", "U1", "16", 3.0, "VDD decoupling"), ("C61", "U1", "32", 3.0, ""), ("C62", "U1", "48", 3.0, ""), ("C63", "U1", "64", 3.0, ""),
    ("C65", "U1", "29", 3.0, "VDDA"), ("C71", "U1", "28", 3.0, "VREF+"), ("C66", "U1", "28", 4.0, "VREF+ bulk"), ("C67", "U1", "7", 3.0, "NRST"),
    ("C80", "U1", "42", 3.0, "CSA filter C at the MCU pin"), ("C81", "U1", "43", 3.0, ""), ("C82", "U1", "11", 3.0, ""),
    ("C90", "U1", "34", 3.0, ""), ("C91", "U1", "35", 3.0, ""), ("C92", "U1", "25", 3.0, ""),
    ("C41", "U1", "18", 3.0, "divider filter at the MCU"), ("C42", "U1", "19", 3.0, ""), ("C43", "U1", "14", 3.0, ""),
    ("C19", "U1", "2", 3.0, "nFAULT filter at PC13"), ("C44", "U1", "20", 4.0, "NTC filter"), ("C68", "U1", "17", 4.0, "pack divider filter"),
    ("C14", "U13", "5", 2.5, "VS cap"), ("C12", "U13", "4", 3.0, "VCAP cap"), ("C18", "U13", "1", 2.5, "EN filter at pin 1"),
    ("C3", "U7", "6", 2.5, "VS cap"), ("C2", "U7", "10", 3.0, "input filter"),
    ("C11", "U8", "15", 2.5, "REGOUT cap 'at the pin'"), ("C9", "U8", "17", 3.0, "BAT cap"),
    ("C40", "U6", "14", 2.5, "decoupling"), ("C17", "U14", "5", 2.5, ""), ("C47", "U9", "8", 2.5, ""), ("C50", "U10", "8", 2.5, ""),
    ("C45", "U11", "5", 3.0, "switch CIN"), ("C46", "U11", "1", 3.0, "switch COUT"), ("C48", "U12", "5", 3.0, ""), ("C49", "U12", "1", 3.0, ""),
    ("C69", "U5", "1", 3.0, "LDO in"), ("C70", "U5", "5", 3.0, "LDO out"),
]


def pad(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == num:
            return p
    raise KeyError((ref, num))


def gap(a, c):
    ra, rc = a.GetBoundingBox(), c.GetBoundingBox()
    dx = max(t(rc.GetLeft() - ra.GetRight()), t(ra.GetLeft() - rc.GetRight()), 0.0)
    dy = max(t(rc.GetTop() - ra.GetBottom()), t(ra.GetTop() - rc.GetBottom()), 0.0)
    return math.hypot(dx, dy)


bad = 0
for part, ic, pin, lim, rule in PAIRS:
    q = pad(ic, pin)
    cands = [p for p in fps[part].Pads() if p.GetNetname() == q.GetNetname()] or list(fps[part].Pads())
    p = min(cands, key=lambda p: math.hypot(t(p.GetPosition().x - q.GetPosition().x), t(p.GetPosition().y - q.GetPosition().y)))
    d = math.hypot(t(p.GetPosition().x - q.GetPosition().x), t(p.GetPosition().y - q.GetPosition().y))
    g = gap(p, q)
    via = fps[part].IsFlipped() != fps[ic].IsFlipped()
    flag = "  <-- over" if lim is not None and g > lim else ""
    bad += bool(flag)
    print(f"{part:5s} -> {ic}.{pin:3s} {q.GetNetname().split('/')[-1]:10s} centre {d:5.2f}  pad gap {g:5.2f} {'via' if via else '   '} (limit {lim}){flag}  {rule}")
print(f"{bad} over the limit")
