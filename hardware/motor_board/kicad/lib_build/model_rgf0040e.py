"""TI RGF0040E VQFN-40 5x7 mm model (SLVSH07 p.92): body 5 x 7 x 0.9 (A max 1.0), terminals
b = 0.25, L = 0.4, pitch 0.5, EP 3.6 x 5.6.  Origin at package centre, seating plane z = 0.
STEP axes: +Y = footprint -y, so pin 1 (footprint -2.4, -2.75) is at (-, +) here."""
import sys
from build123d import *

A, BX, BY = 0.9, 5.0, 7.0
b, L, t = 0.25, 0.4, 0.2
term = []
for i in range(12):  # 1-12 left, footprint top->bottom = STEP +Y -> -Y
    term.append((-BX / 2 + L / 2, 2.75 - 0.5 * i, L, b))
for i in range(8):   # 13-20 bottom (STEP -Y), left->right
    term.append((-1.75 + 0.5 * i, -BY / 2 + L / 2, b, L))
for i in range(12):  # 21-32 right, bottom->top
    term.append((BX / 2 - L / 2, -2.75 + 0.5 * i, L, b))
for i in range(8):   # 33-40 top (STEP +Y), right->left
    term.append((1.75 - 0.5 * i, BY / 2 - L / 2, b, L))

pads = [Box(w, h, t, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Location((x, y, 0)))
        for x, y, w, h in term]
pads.append(Box(3.6, 5.6, t, align=(Align.CENTER, Align.CENTER, Align.MIN)))
metal = pads[0]
for p in pads[1:]:
    metal = metal + p
body = Box(BX, BY, A, align=(Align.CENTER, Align.CENTER, Align.MIN)) - metal
# pin-1 dimple on top
body = body - Cylinder(0.25, 0.05, align=(Align.CENTER, Align.CENTER, Align.MAX)).moved(
    Location((-BX / 2 + 0.7, BY / 2 - 0.7, A)))
body.color = Color(0.15, 0.15, 0.15)
body.label = "body"
metal.color = Color(0.82, 0.82, 0.78)
metal.label = "pins"
asm = Compound(children=[body, metal], label="TI_RGF0040E_VQFN-40")
export_step(asm, sys.argv[1])
print(asm.bounding_box())
