from build123d import *
import os
D = os.path.dirname(os.path.abspath(__file__))
os.makedirs(D, exist_ok=True)
BODY = Color(0.15, 0.15, 0.15)
PIN = Color(0.82, 0.82, 0.78)
MARK = Color(0.9, 0.9, 0.9)
CU = Color(0.85, 0.5, 0.2)

def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)

def save(parts, name):
    objs = []
    for i, (shape, col, lbl) in enumerate(parts):
        shape.color = col
        shape.label = lbl
        objs.append(shape)
    c = Compound(children=objs)
    c.label = name
    p = f"{D}/{name}.step"
    export_step(c, p)
    print(p, c.bounding_box())

# model coords: Y up (KiCad footprint Y is down) -> pad (x, y) => model (x, -y)

def wqfn14_bqa():
    # ---- TI BQA0014A WQFN-14 2.5 x 3.0, P0.5, EP 1.0 x 1.5, 0.8 max (U6, SN74LVC08ABQAR) ----
    # pads (footprint DHWQFN-14-1EP_2.5x3mm): 1 / 14 at x -+0.25 on the top short side, 2-6 left (y -1..1),
    # 7 / 8 bottom short side, 9-13 right (y 1..-1)
    H, L, W, T = 0.75, 0.4, 0.25, 0.2
    body = box(-1.25, 1.25, -1.5, 1.5, 0.02, H)
    dot = Pos(-0.75, 1.1, H) * Cylinder(0.12, 0.02)
    pins = []
    for i in range(5):
        y = 1.0 - 0.5 * i                                                  # model Y up: pad 2 (fp y -1) at +1
        pins.append(box(-1.25, -1.25 + L, y - W/2, y + W/2, 0, T))        # left 2-6
        pins.append(box(1.25 - L, 1.25, y - W/2, y + W/2, 0, T))          # right 13-9
    for x in (-0.25, 0.25):
        pins.append(box(x - W/2, x + W/2, 1.5 - L, 1.5, 0, T))            # 1 / 14
        pins.append(box(x - W/2, x + W/2, -1.5, -1.5 + L, 0, T))          # 7 / 8
    ep = box(-0.5, 0.5, -0.75, 0.75, 0, T)
    body = body - Compound(pins) - ep
    save([(body, BODY, "body"), (Compound(pins + [ep]), PIN, "pins"), (dot, MARK, "pin1")],
         "DHWQFN-14-1EP_2.5x3mm_P0.5mm_EP1x1.5mm")


import sys
if sys.argv[1:] == ["wqfn14"]:
    wqfn14_bqa()
    raise SystemExit
wqfn14_bqa()


# ---- QFN-20 3.5x3.5 P0.5 EP2x2 (TI RGR, VQFN 0.9 typ / 1.0 max) ----
H = 0.9
body = box(-1.75, 1.75, -1.75, 1.75, 0.02, H)
dot = Pos(-1.2, 1.2, H) * Cylinder(0.15, 0.02)
pins = []
L, W, T = 0.4, 0.25, 0.2
for i in range(5):
    y = 1.0 - 0.5 * i          # pins 1..5 on left, top to bottom (model Y up)
    pins.append(box(-1.75, -1.75 + L, y - W/2, y + W/2, 0, T))           # left 1-5
    x = -1.0 + 0.5 * i
    pins.append(box(x - W/2, x + W/2, -1.75, -1.75 + L, 0, T))           # bottom 6-10
    pins.append(box(1.75 - L, 1.75, -y - W/2, -y + W/2, 0, T))           # right 11-15
    pins.append(box(-x - W/2, -x + W/2, 1.75 - L, 1.75, 0, T))           # top 16-20
ep = box(-1.025, 1.025, -1.025, 1.025, 0, T)
body = body - Compound(pins) - ep
save([(body, BODY, "body"), (Compound(pins + [ep]), PIN, "pins"), (dot, MARK, "pin1")],
     "QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm")

# ---- TI DDF0008A SOT-23-8 thin: body 1.6 x 2.9, span 2.8, h 1.1 max ----
BH0, BH1 = 0.05, 1.0
body = box(-0.8, 0.8, -1.45, 1.45, BH0, BH1)
dot = Pos(-0.4, 1.05, BH1) * Cylinder(0.12, 0.02)
leads = []
t, w = 0.13, 0.3
for i in range(4):
    y = 0.975 - 0.65 * i
    for s in (-1, 1):
        a = box(0.8, 1.0, y - w/2, y + w/2, 0.45, 0.45 + t)     # arm out of body
        b = box(1.0 - t, 1.0, y - w/2, y + w/2, 0, 0.45 + t)     # bend down
        f = box(1.0 - t, 1.4, y - w/2, y + w/2, 0, t)            # foot
        lead = a + b + f
        if s < 0:
            lead = mirror(lead, Plane.YZ)
        leads.append(lead)
save([(body, BODY, "body"), (Compound(leads), PIN, "leads"), (dot, MARK, "pin1")],
     "Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm")

# ---- Solder-wire stubs: insulated wire standing up, conductor through the hole ----
for name, dc, od in (("SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm", 0.9, 2.1),
                     ("SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm", 1.7, 3.9)):
    ins = Pos(0, 0, 1.0 + 5.0) * Cylinder(od / 2, 10.0)       # z 1..11 (strip gap 1 mm)
    cond = Pos(0, 0, (-2.0 + 1.5) / 2) * Cylinder(dc / 2, 3.5)  # z -2..1.5 (through a 1.6 mm board)
    save([(ins, Color(0.1, 0.1, 0.1), "insulation"), (cond, CU, "conductor")], name)
