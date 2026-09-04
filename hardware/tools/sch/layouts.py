"""Per-sheet placement for the ThumbsUp schematic.

Each ``draw_<sheet>`` function receives the SKiDL ``Design`` and a ``Sheet``
and places parts explicitly.  Anything not wired by hand is finished by
``Sheet.finish()`` (power symbols / labels / no-connects).  Plain decoupling
capacitors are drawn in a strip at the bottom of each sheet, the way a hand
drawn schematic would, with a note that they belong at the IC pins.
"""

from __future__ import annotations

from draw import G, Sheet

ROW = 15.24  # vertical pitch between stacked passive blocks


# ---------------------------------------------------------------- idioms
def decap_strip(s: Sheet, d, refs, x0: float, y: float, title: str = "Decoupling — place at the IC pins"):
    """Row of vertical caps: rail symbol on top, GND below."""
    s.text(x0 - 2.54, y - 12.7, title, size=1.5, bold=True)
    for i, ref in enumerate(refs):
        c = d.by_ref(ref)
        x = x0 + i * 12.7
        s.place(c, x, y)
        s.power(s.pin(c, 1))
        s.power(s.pin(c, 2))


def series_v(s: Sheet, parts_pins, x: float, y0: float):
    """Vertical chain of two-pin parts, top to bottom; returns node points."""
    nodes = []
    y = y0
    prev = None
    for part, top, bottom, rot in parts_pins:
        s.place_pin_at(part, top, (x, y), rot)
        if prev is not None:
            s.wire(prev, s.pin(part, top))
        prev = s.pin(part, bottom)
        nodes.append((x, y))
        y = prev.y + 2.54
    return nodes


def rc_to_gnd(s: Sheet, cap, node, dx: float = 10.16):
    """Capacitor from ``node`` (a point) to GND, hanging to the right."""
    x, y = node[0] + dx, node[1]
    s.place_pin_at(cap, 1, (x, y + 2.54))
    s.wire(node, (x, y), s.pin(cap, 1))
    s.power(s.pin(cap, 2))


# ---------------------------------------------------------------- sheets
def draw_pack(d, s: Sheet):
    s.text(20, 25, "Pack input: XT30 → TVS/filter → POWER LINK J4 → 1 mΩ shunt (Kelvin net-ties) → VBAT (bridges) ; VBAT → P-FET reverse-polarity → +VDRV (logic)", 2, True)
    s.text(20, 31, "J1: '+' is pad 2 on the KiCad AMASS footprint.  Motor path is polarised by the connector only (PWR-3): a reversed pack destroys the board.  Q1: pack on DRAIN, load on SOURCE.", 1.5)
    j1 = d.by_ref("J1")
    s.place(j1, 33.02, 110.49)
    p1, p2 = s.pin(j1, 1), s.pin(j1, 2)
    bus_y = p2.y  # pin 2 = '+'
    s.wire(p2, (104.14, bus_y))
    s.power(p1)
    s.flag((43.18, bus_y))
    s.wire((48.26, bus_y), (48.26, bus_y - 2.54))
    s.power_at((48.26, bus_y - 2.54), "VBAT_PACK", came_from=(0, 1))
    # power link: both pins point down onto the bus line; pin 2 (left) is the pack side
    j4 = d.by_ref("J4")
    s.place_pin_at(j4, 2, (104.14, bus_y - 2.54), 270)
    s.wire(s.pin(j4, 2), (104.14, bus_y))
    s.wire(s.pin(j4, 1), (106.68, bus_y), (114.3, bus_y))
    s.flag((109.22, bus_y))
    s.text(92, bus_y - 16, "J4 POWER LINK = SPARC disconnect (PWR-2)", 1.27)
    # TVS + entry caps hang from the bus
    for ref, x, rot in (("D1", 55.88, 270), ("C1", 66.04, 0), ("C2", 74.93, 0), ("C3", 83.82, 0), ("C4", 93.98, 0)):
        c = d.by_ref(ref)
        top = 1  # K for the zener-style TVS, pin 1 for caps
        s.place_pin_at(c, top, (x, bus_y + 2.54), rot)
        s.wire((x, bus_y), s.pin(c, top))
        s.power(s.pin(c, 2))
    # shunt
    r2 = d.by_ref("R2")
    s.place_pin_at(r2, 1, (116.84, bus_y), 90)
    s.wire((114.3, bus_y), s.pin(r2, 1))
    s.power_at((114.3, bus_y), "VBAT_LINK", came_from=(0, -1)) if False else None
    for nt_ref, xr, lbl in (("NT1", 114.3, "PACK_S+"), ("NT2", 127.0, "PACK_S-")):
        nt = d.by_ref(nt_ref)
        s.place_pin_at(nt, 1, (xr, bus_y + 2.54), 90)   # pin 1 down onto the bus node, pin 2 up
        s.wire((xr, bus_y), s.pin(nt, 1))
        s.label(s.pin(nt, 2))
    s.text(100, bus_y + 17, "NT1/NT2: Kelvin net-ties on the R2 pads; PACK_S+/- to U4 leave from them", 1.27)
    q1 = d.by_ref("Q1")
    s.place_pin_at(q1, "D", (139.7, bus_y), 90)
    s.wire(s.pin(r2, 2), s.pin(q1, "D"))
    s.flag((132.08, bus_y))
    vb = s.pin(q1, "D").out()
    s.power_at((132.08, bus_y - 2.54), "VBAT", came_from=(0, 1))
    s.wire((132.08, bus_y), (132.08, bus_y - 2.54))
    # gate network
    g = s.pin(q1, "G")
    gn = s.stub(g)
    r1 = d.by_ref("R1")
    s.place_pin_at(r1, 1, (gn[0], gn[1] + 2.54))
    s.wire(gn, s.pin(r1, 1))
    s.power(s.pin(r1, 2))
    dz = d.by_ref("D2")
    s.place_pin_at(dz, "A", (gn[0] + 5.08, gn[1]), 180)  # A left, K right
    s.wire(gn, s.pin(dz, "A"))
    src = s.pin(q1, "S")
    so = s.stub(src)
    s.wire(s.pin(dz, "K"), (s.pin(dz, "K").out()[0], so[1]), so)
    # +VDRV
    s.wire(so, (177.8, so[1]))
    c5 = d.by_ref("C5")
    s.place_pin_at(c5, 1, (170.18, so[1] + 2.54))
    s.wire((170.18, so[1]), s.pin(c5, 1))
    s.power(s.pin(c5, 2))
    s.power_at((177.8, so[1]), "+VDRV", came_from=(1, 0))
    s.flag((162.56, so[1]))
    s.text(150, bus_y + 25.4, "+VDRV feeds the 5 V buck and the FD6288 gate drivers (9–12.6 V).", 1.27)
    s.text(30, 165, "Mechanical: 4x M3 mounting holes, 3 fiducials (positions from the chassis in layout)", 1.5, True)
    for i, ref in enumerate(("H1", "H2", "H3", "H4", "FID1", "FID2", "FID3")):
        s.place(d.by_ref(ref), 38.1 + i * 15.24, 175.26)
    # ground reference flag for ERC
    s.wire((25.4, bus_y + 30.48), (25.4, bus_y + 33.02))
    s.flag((25.4, bus_y + 30.48))
    s.power_at((25.4, bus_y + 33.02), "GND", up=False, came_from=(0, 1))


def draw_rails(d, s: Sheet):
    s.text(20, 25, "Rails: +VDRV → AP63205 5 V/2 A → (D3) Pico VSYS ; +5V → AP2112 ×2 → +3V3_A (sensors) and +3V3_MCU (3× AT32, flash)", 2, True)
    s.text(20, 31, "FB is tied to VOUT: AP63205 is the fixed-5 V part and regulates on FB (DS Fig. 21).  EN divider 100k/20k → on ≈6.9 V, off ≈6.05 V (incl. 1.5/4 µA EN currents).", 1.5)
    u1 = d.by_ref("U1")
    s.place(u1, 91.44, 88.9)
    pin_in, en, sw, bst, fb, gnd = (s.pin(u1, n) for n in ("IN", "EN", "SW", "BST", "FB", "GND"))
    # input rail
    rail_y = pin_in.y
    io = s.stub(pin_in)
    s.wire(io, (35.56, rail_y))
    s.power_at((35.56, rail_y), "+VDRV", came_from=(-1, 0))
    for ref, x in (("C10", 45.72), ("C11", 55.88), ("C12", 66.04)):
        c = d.by_ref(ref)
        s.place_pin_at(c, 1, (x, rail_y + 2.54))
        s.wire((x, rail_y), s.pin(c, 1))
        s.power(s.pin(c, 2))
    # EN divider
    r10, r11 = d.by_ref("R10"), d.by_ref("R11")
    s.place_pin_at(r10, 1, (73.66, rail_y + 2.54))
    s.wire((73.66, rail_y), s.pin(r10, 1))
    eo = s.stub(en)
    n = s.pin(r10, 2).out()
    s.wire(s.pin(r10, 2), (n[0], eo[1] + 5.08), (eo[0], eo[1] + 5.08), eo)
    s.place_pin_at(r11, 1, (n[0], n[1] + 2.54))
    s.wire(n, s.pin(r11, 1))
    s.power(s.pin(r11, 2))
    s.power(gnd)
    # switch node, bootstrap, inductor, output
    swo = s.stub(sw)
    top_y = rail_y - 12.7
    s.wire(swo, (swo[0] + 2.54, swo[1]), (swo[0] + 2.54, top_y), (119.38, top_y))
    l1 = d.by_ref("L1")
    s.place_pin_at(l1, 1, (119.38, top_y), 90)
    c13 = d.by_ref("C13")
    bo = s.stub(bst)
    s.place_pin_at(c13, 1, (bo[0] + 2.54, bo[1]), 90)
    s.wire(bo, s.pin(c13, 1))
    c13b = s.pin(c13, 2).out()
    s.wire(s.pin(c13, 2), (c13b[0], top_y))
    out_x0 = s.pin(l1, 2).out()[0]
    s.wire(s.pin(l1, 2), (170.18, top_y))
    for ref, x in (("C14", 134.62), ("C15", 144.78)):
        c = d.by_ref(ref)
        s.place_pin_at(c, 1, (x, top_y + 2.54))
        s.wire((x, top_y), s.pin(c, 1))
        s.power(s.pin(c, 2))
    fo = s.stub(fb)
    s.wire(fo, (fo[0], fo[1] + 10.16), (154.94, fo[1] + 10.16), (154.94, top_y))
    s.text(101, fo[1] + 14, "FB → VOUT (fixed 5 V part)", 1.27)
    s.flag((160.02, top_y))
    s.power_at((170.18, top_y), "+5V", came_from=(1, 0))
    # VSYS diode
    d3 = d.by_ref("D3")
    s.place_pin_at(d3, "A", (198.12, top_y), 180)
    s.power_at((195.58, top_y), "+5V", came_from=(-1, 0))
    s.wire((195.58, top_y), s.pin(d3, "A"))
    ko = s.stub(s.pin(d3, "K"))
    s.wire(ko, (ko[0] + 5.08, ko[1]))
    s.flag((ko[0] + 2.54, ko[1]))
    s.power_at((ko[0] + 5.08, ko[1]), "+5V_PICO", came_from=(1, 0))
    s.text(190, top_y + 6.35, "USB VBUS cannot back-feed +5V / +VDRV", 1.27)

    # LDOs
    for ref, cin, cout, y, rail in (("U2", "C16", "C17", 139.7, "+3V3_A"), ("U3", "C18", "C19", 172.72, "+3V3_MCU")):
        u = d.by_ref(ref)
        s.place(u, 91.44, y)
        vin, en_, gnd_, nc, vout = (s.pin(u, n) for n in ("VIN", "EN", "GND", "NC", "VOUT"))
        vo = s.stub(vin)
        eo = s.stub(en_)
        s.wire(eo, vo)
        s.wire(vo, (60.96, vo[1]))
        s.power_at((60.96, vo[1]), "+5V", came_from=(-1, 0))
        c = d.by_ref(cin)
        s.place_pin_at(c, 1, (68.58, vo[1] + 2.54))
        s.wire((68.58, vo[1]), s.pin(c, 1))
        s.power(s.pin(c, 2))
        s.power(gnd_)
        s.nc(nc)
        oo = s.stub(vout)
        s.wire(oo, (124.46, oo[1]))
        c = d.by_ref(cout)
        s.place_pin_at(c, 1, (114.3, oo[1] + 2.54))
        s.wire((114.3, oo[1]), s.pin(c, 1))
        s.power(s.pin(c, 2))
        s.power_at((124.46, oo[1]), rail, came_from=(1, 0))

    # monitors
    s.text(205, 117, "Pack voltage → GP26 (12.6 V → 2.27 V)", 1.5, True)
    r12, r13, c20 = d.by_ref("R12"), d.by_ref("R13"), d.by_ref("C20")
    s.place_pin_at(r12, 1, (218.44, 127))
    s.power(s.pin(r12, 1))
    node = s.pin(r12, 2).out()
    s.place_pin_at(r13, 1, (node[0], node[1] + 2.54))
    s.wire(s.pin(r12, 2), s.pin(r13, 1))
    s.power(s.pin(r13, 2))
    rc_to_gnd(s, c20, node)
    s.label_at(node, "PACK_V_ADC", 180)

    s.text(255, 117, "+3V3_A monitor → GP27 (1:1)", 1.5, True)
    r14, r15, c21 = d.by_ref("R14"), d.by_ref("R15"), d.by_ref("C21")
    s.place_pin_at(r14, 1, (266.7, 127))
    s.power(s.pin(r14, 1))
    node = s.pin(r14, 2).out()
    s.place_pin_at(r15, 1, (node[0], node[1] + 2.54))
    s.wire(s.pin(r14, 2), s.pin(r15, 1))
    s.power(s.pin(r15, 2))
    rc_to_gnd(s, c21, node)
    s.label_at(node, "3V3_MON", 180)

    s.text(30, 205, "Test points", 1.5, True)
    for i in range(1, 7):
        s.place(d.by_ref(f"TP{i}"), 38.1 + (i - 1) * 15.24, 213.36)
    # power LED
    s.text(205, 162, "Pack-present LED from +VDRV — independent of firmware (C-7)", 1.5, True)
    r16, d4 = d.by_ref("R16"), d.by_ref("D4")
    s.place_pin_at(r16, 1, (218.44, 172.72))
    s.power(s.pin(r16, 1))
    s.place_pin_at(d4, "A", (218.44, s.pin(r16, 2).out()[1]), 90)
    s.wire(s.pin(r16, 2), s.pin(d4, "A"))
    s.power(s.pin(d4, "K"))


def draw_pico(d, s: Sheet):
    s.text(20, 25, "Pico W — Bluetooth, DShot ×3, I2C sensors, SPI log flash, ADC monitors, safety I/O", 2, True)
    s.text(20, 31, "All GPIO per PINMAP.md.  VSYS comes from +5V through D3; VBUS/3V3/3V3_EN unused (3V3_EN floating = enabled).", 1.5)
    a1 = d.by_ref("A1")
    s.place(a1, 152.4, 130.81)
    for n in ("VBUS", "3V3_EN", "ADC_VREF"):
        s.nc(s.pin(a1, n))
    s.power(s.pin(a1, "3V3"))
    s.power(s.pin(a1, "VSYS"))
    s.power(s.pin(a1, 3))
    s.power(s.pin(a1, "AGND"))
    # unused GPIO -> NC, everything else labelled by finish()
    for n in ("GPIO5", "GPIO14", "GPIO15", "GPIO20", "GPIO21"):
        s.nc(s.pin(a1, n))

    # I2C pull-ups
    s.text(30, 187, "I2C pull-ups", 1.5, True)
    for ref, x, name in (("R20", 38.1, "I2C1_SDA"), ("R21", 50.8, "I2C1_SCL")):
        r = d.by_ref(ref)
        s.place_pin_at(r, 1, (x, 198.12))
        s.power(s.pin(r, 1))
        s.label(s.pin(r, 2))

    # ARM link
    s.text(75, 187, "ARM link — physical plug to GND; sensed by GP8, gates weapon VCC", 1.5, True)
    r22, c23, j2 = d.by_ref("R22"), d.by_ref("C23"), d.by_ref("J2")
    s.place_pin_at(r22, 1, (83.82, 198.12))
    s.power(s.pin(r22, 1))
    node = s.pin(r22, 2).out()
    s.wire(s.pin(r22, 2), (node[0], node[1] + 2.54))
    s.label_at((node[0], node[1] + 2.54), "ARM_N", 270)
    rc_to_gnd(s, c23, node)
    s.place_pin_at(j2, 1, (node[0] + 25.4, node[1]), 180)  # pins exit left toward the node
    s.wire(node, s.pin(j2, 1))
    s.power(s.pin(j2, 2))

    # reset
    s.text(150, 187, "Reset (100 nF: ESD/EMI on the RUN stub)", 1.5, True)
    sw = d.by_ref("SW1")
    s.place(sw, 175.26, 198.12)
    node = s.stub(s.pin(sw, 1))
    s.wire(node, (node[0] - 5.08, node[1]))
    s.label_at((node[0] - 5.08, node[1]), "RUN", 180)
    rc_to_gnd(s, d.by_ref("C25"), node, -2.54) if False else None
    c25 = d.by_ref("C25")
    s.place_pin_at(c25, 1, (node[0] - 2.54, node[1] + 2.54))
    s.wire((node[0] - 2.54, node[1]), s.pin(c25, 1))
    s.power(s.pin(c25, 2))
    s.power(s.pin(sw, 2))
    # DShot series resistors and test points
    s.text(30, 225, "DShot series 100 Ω (push-pull contention limit, both ends)", 1.5, True)
    for i, ref in enumerate(("R24", "R25", "R26")):
        r = d.by_ref(ref)
        s.place_pin_at(r, 1, (38.1 + i * 15.24, 233.68))
        s.label(s.pin(r, 1))
        s.label(s.pin(r, 2))
    s.text(110, 225, "Test points", 1.5, True)
    for i in range(10, 16):
        s.place(d.by_ref(f"TP{i}"), 118.11 + (i - 10) * 15.24, 236.22)

    # NTC
    s.text(205, 187, "Board NTC at weapon FETs → GP28", 1.5, True)
    th, r23, c24 = d.by_ref("TH1"), d.by_ref("R23"), d.by_ref("C24")
    s.place_pin_at(th, 1, (213.36, 198.12))
    s.power(s.pin(th, 1))
    node = s.pin(th, 2).out()
    s.place_pin_at(r23, 1, (node[0], node[1] + 2.54))
    s.wire(s.pin(th, 2), s.pin(r23, 1))
    s.power(s.pin(r23, 2))
    rc_to_gnd(s, c24, node)
    s.label_at(node, "NTC_ADC", 180)

    # expansion header
    s.text(260, 187, "Expansion (autonomy card)", 1.5, True)
    j3 = d.by_ref("J3")
    s.place(j3, 279.4, 205.74)


def draw_sense(d, s: Sheet):
    s.text(20, 25, "Instrumentation: INA226 ×4 on I2C1 (pack high-side 0x40, per-cell low-side 0x41/0x44/0x45), LSM6DS3TR-C (0x6A), ADXL375 (0x53)", 2, True)
    s.text(20, 31, "10 Ω + 100 nF differential filters on every shunt input (TI INA226 DS §8.2.2).  Vin− of the cell channels is the shunt's ground end (Kelvin).", 1.5)
    xs = (50.8, 116.84, 182.88, 248.92)
    for i, ref in enumerate(("U4", "U5", "U6", "U7")):
        u = d.by_ref(ref)
        x, y = xs[i], 78.74
        s.place(u, x, y)
        s.power(s.pin(u, "VS"))
        s.power(s.pin(u, "GND"))
        n = 3 + i
        rp, rm = d.by_ref(f"R{n}0"), d.by_ref(f"R{n}1")
        cf = d.by_ref(f"C{n}1")
        po = s.stub(s.pin(u, "Vin+"))
        mo = s.stub(s.pin(u, "Vin-"))
        s.wire(po, (po[0] - 2.54, po[1]))
        s.place_pin_at(rp, 2, (po[0] - 5.08, po[1]), 90)
        s.wire((po[0] - 2.54, po[1]), s.pin(rp, 2))
        low_y = mo[1] + 7.62
        cx = po[0] - 2.54
        s.wire(mo, (mo[0], low_y), (cx, low_y))              # ends at the filter cap's pin 2
        s.wire((cx, low_y), (po[0] - 5.08 - 2.54, low_y))
        s.place_pin_at(rm, 2, (po[0] - 5.08 - 2.54, low_y), 90)
        s.place_pin_at(cf, 1, (cx, po[1] + 2.54))
        s._cover(s.pin(cf, 2))  # pin 2 is a wire endpoint at (cx, low_y)
        s.text(x - 40, y + 17.78, "Kelvin", 1.27)

    lsm = d.by_ref("U8")
    s.place(lsm, 63.5, 165.1)
    a = s.stub(s.pin(lsm, "VDDIO"))
    b = s.stub(s.pin(lsm, "VDD"))
    s.wire(a, b)
    s.power_at(a, "+3V3_A", came_from=(0, 1))
    s.power(s.pin(lsm, 6))
    for n in ("SDO/SA0", "SDX", "SCX"):
        s.power(s.pin(lsm, n))
    s.power(s.pin(lsm, "CS"))
    s.text(40, 185, "SDx/SCx: connect to VDDIO or GND (DS Table 2)", 1.27)
    adxl = d.by_ref("U9")
    s.place(adxl, 139.7, 165.1)
    a = s.stub(s.pin(adxl, "Vs"))
    b = s.stub(s.pin(adxl, "Vdd_I/O"))
    s.wire(a, b)
    s.power_at(a, "+3V3_A", came_from=(0, 1))
    s.power(s.pin(adxl, 2))
    s.power(s.pin(adxl, "~{CS}"))
    s.power(s.pin(adxl, "SDO/ADDR"))
    s.text(120, 185, "RES pins: open (DS).  1 µF at VS, 100 nF at VDD I/O", 1.27)
    decap_strip(s, d, ("C30", "C40", "C50", "C60", "C70", "C71", "C72", "C73"), 200.66, 165.1)


def draw_io(d, s: Sheet):
    s.text(20, 25, "Match-log flash (SPI0) and status LEDs (SK6812 ×2 via 74AHCT1G125 level shifter)", 2, True)
    s.text(20, 31, "CS/WP/HOLD pulled to +3V3_MCU so the flash is deselected while the Pico boots.  SK6812 VIH = 0.7·VDD, so Pico 3.3 V needs the 5 V buffer.", 1.5)
    fl = d.by_ref("U10")
    s.place(fl, 76.2, 96.52)
    s.power(s.pin(fl, 8))
    s.power(s.pin(fl, 4))
    s.text(40, 118, "Pull-ups to +3V3_MCU", 1.5, True)
    for ref, x in (("R80", 45.72), ("R81", 58.42), ("R82", 71.12)):
        r = d.by_ref(ref)
        s.place_pin_at(r, 1, (x, 127))
        s.power(s.pin(r, 1))
        s.label(s.pin(r, 2))

    buf = d.by_ref("U11")
    s.place(buf, 177.8, 96.52)
    s.power(s.pin(buf, 1))  # OE low = enabled
    s.power(s.pin(buf, "VCC"))
    s.power(s.pin(buf, "GND"))
    r53 = d.by_ref("R83")
    yo = s.stub(s.pin(buf, 4))
    s.place_pin_at(r53, 1, (yo[0] + 2.54, yo[1]), 90)
    s.wire(yo, s.pin(r53, 1))
    led1, led2 = d.by_ref("D5"), d.by_ref("D6")
    s.place_pin_at(led1, "DIN", (s.pin(r53, 2).out()[0] + 10.16, yo[1]))
    s.wire(s.pin(r53, 2), s.pin(led1, "DIN"))
    s.place_pin_at(led2, "DIN", (s.pin(led1, "DOUT").out()[0] + 12.7, yo[1]))
    s.wire(s.pin(led1, "DOUT"), s.pin(led2, "DIN"))
    for l in (led1, led2):
        s.power(s.pin(l, "VDD"))
        s.power(s.pin(l, "GND"))
    s.text(215, 112, "D5 = system status, D6 = weapon status", 1.27)
    decap_strip(s, d, ("C80", "C81", "C82", "C83"), 63.5, 165.1)


def draw_esc(d, s: Sheet, k: str, base: int):
    vcc_name = "W_VCC" if k == "W" else "+VDRV"
    s.text(20, 25, f"ESC {k}: AM32 cell — AT32F421 (target AT32DEV_F421) + FD6288Q gate driver + sense networks.  Power stage on sheet esc_{k.lower()}_bridge.", 2, True)
    s.text(20, 31, "Stock-hex scaling: voltage divider 100k/10k (TARGET_VOLTAGE_DIVIDER 110), current 1 mΩ × INA180A1 (20 V/V) = 20 mV/A (MILLIVOLT_PER_AMP 20).", 1.5)
    u = base // 10
    mcu, drv, csa = d.by_ref(f"U{u}"), d.by_ref(f"U{u + 1}"), d.by_ref(f"U{u + 2}")
    s.place(mcu, 99.06, 106.68)
    # power pins joined
    vdd, vdd2, vdda = s.pin(mcu, "VDD"), s.pin(mcu, "VDD2"), s.pin(mcu, "VDDA")
    a = s.stub(vdd, 5.08)
    b = s.stub(vdd2, 5.08)
    c = s.stub(vdda, 5.08)
    s.wire(a, c)
    s.power_at(a, "+3V3_MCU", came_from=(-1, 0))
    s.power(s.pin(mcu, "EP_VSS"))
    # NRST with cap, BOOT0 pull-down
    nr = s.stub(s.pin(mcu, "NRST"), 5.08)
    cn = d.by_ref(f"C{base + 5}")
    s.place_pin_at(cn, 1, (nr[0] - 5.08, nr[1] + 2.54))
    s.wire(nr, (nr[0] - 5.08, nr[1]), s.pin(cn, 1))
    s.power(s.pin(cn, 2))
    s.wire(nr, (nr[0] - 10.16, nr[1]))
    s.label_at((nr[0] - 10.16, nr[1]), f"{k}_NRST", 180)
    bo = s.stub(s.pin(mcu, "BOOT0"))
    rb = d.by_ref(f"R{base}")
    s.place_pin_at(rb, 1, (bo[0] - 2.54, bo[1]), 270)
    s.wire(bo, s.pin(rb, 1))
    s.power(s.pin(rb, 2))

    # gate driver
    s.place(drv, 205.74, 106.68)
    s.power(s.pin(drv, "VCC"))
    s.power(s.pin(drv, "COM"))
    s.text(190, 132, "HO/LO/VS/VB → bridge sheet", 1.27)

    # SWD header
    j = d.by_ref(f"J{u}")
    s.text(30, 146, "SWD (first bootloader flash)", 1.5, True)
    s.place(j, 38.1, 160.02)
    s.text(30, 175, "1: +3V3  2: SWDIO  3: SWCLK  4: NRST  5: GND", 1.27)

    # DShot pull-down
    s.text(30, 183, "DShot pull-down — DNP (AT32 idles high for AM32 1-wire)", 1.5, True)
    rpd = d.by_ref(f"R{base + 1}")
    s.place_pin_at(rpd, 1, (40.64, 193.04))
    s.label(s.pin(rpd, 1))
    s.power(s.pin(rpd, 2))

    # voltage divider
    s.text(75, 146, "Pack voltage → PA6 (11:1)", 1.5, True)
    rvh, rvl, cv = d.by_ref(f"R{base + 2}"), d.by_ref(f"R{base + 3}"), d.by_ref(f"C{base + 6}")
    s.place_pin_at(rvh, 1, (83.82, 157.48))
    s.power(s.pin(rvh, 1))
    node = s.pin(rvh, 2).out()
    s.place_pin_at(rvl, 1, (node[0], node[1] + 2.54))
    s.wire(s.pin(rvh, 2), s.pin(rvl, 1))
    s.power(s.pin(rvl, 2))
    rc_to_gnd(s, cv, node)
    s.label_at(node, f"{k}_VSENSE", 180)

    # current sense amplifier
    s.text(120, 146, "Cell current: 1 mΩ shunt → INA180A1 (20 V/V) → RC → PA3", 1.5, True)
    s.place(csa, 139.7, 165.1)
    s.power(s.pin(csa, "V+"))
    s.power(s.pin(csa, "GND"))
    s.label(s.pin(csa, "-"))
    s.label(s.pin(csa, "+"))
    rrc, crc = d.by_ref(f"R{base + 4}"), d.by_ref(f"C{base + 7}")
    oo = s.stub(s.pin(csa, 1))
    s.place_pin_at(rrc, 1, (oo[0] + 2.54, oo[1]), 90)
    s.wire(oo, s.pin(rrc, 1))
    node = s.pin(rrc, 2).out()
    s.wire(s.pin(rrc, 2), node)
    rc_to_gnd(s, crc, node, 5.08)
    s.wire(node, (node[0] + 7.62, node[1]))
    s.label_at((node[0] + 7.62, node[1]), f"{k}_ISENSE", 0)

    # BEMF dividers + virtual neutral
    s.text(200, 146, "BEMF dividers 10k/3.3k (4:1) and 10k virtual-neutral star → comparator", 1.5, True)
    for i, ph in enumerate("ABC"):
        rt, rbm, rvn = d.by_ref(f"R{base + 5 + i}"), d.by_ref(f"R{base + 8 + i}"), d.by_ref(f"R{base + 11 + i}")
        x = 213.36 + i * 33.02
        s.place_pin_at(rt, 1, (x, 157.48))
        s.label(s.pin(rt, 1))
        node = s.pin(rt, 2).out()
        s.place_pin_at(rbm, 1, (x, node[1] + 2.54))
        s.wire(s.pin(rt, 2), s.pin(rbm, 1))
        s.power(s.pin(rbm, 2))
        s.place_pin_at(rvn, 1, (x + 10.16, node[1] + 2.54), 0)
        s.wire(node, (x + 10.16, node[1]), s.pin(rvn, 1))
        s.label(s.pin(rvn, 2))
        s.label_at(node, f"{k}_BEMF_{ph}", 180)

    decap_strip(s, d, [f"C{base + n}" for n in (0, 1, 2, 3, 4, 8, 9, 10)], 218.44, 210.82, "Decoupling — at U pins (C%d…: AT32 VDD/VDDA, INA180, FD6288 VCC)" % base)
    s.text(120, 183, "Test points (PB6 = AM32 KISS telemetry, 115200)", 1.5, True)
    for i in range(3):
        s.place(d.by_ref(f"TP{u}{i}"), 127.0 + i * 15.24, 193.04)


def draw_weapon_enable(d, s: Sheet):
    """Extra block on the weapon ctrl sheet."""
    s.text(20, 215, "Weapon hardware enable: W_VCC = +VDRV only when WEAPON_EN (GP9) AND ARM link closed.  Q49 (from the gate node) and Q50 (from ARM_N) hold the AT32 in reset while disabled,", 1.5, True)
    s.text(20, 220, "so no 3.3 V is ever driven into an unpowered FD6288 (abs max VIN <= VCC+0.3 V).  R440 4.7k keeps Vsg(Q46) < 0.45 V when off (SPICE); R442 keeps the weapon off if the Pico pin floats.", 1.5)
    qp, qn, qi, qr, qr2 = (d.by_ref(r) for r in ("Q46", "Q47", "Q48", "Q49", "Q50"))
    rpu, rens, renpd, rrh, rrl = (d.by_ref(r) for r in ("R440", "R441", "R442", "R443", "R444"))
    x0, y0 = 71.12, 238.76
    s.place(qp, x0, y0, 90)  # D left, S right, G bottom
    src, drn = s.pin(qp, "S"), s.pin(qp, "D")
    so = s.stub(src)
    do = s.stub(drn)
    s.wire(do, (do[0] - 7.62, do[1]))
    s.flag((do[0] - 5.08, do[1]))
    s.power_at((do[0] - 7.62, do[1]), "W_VCC", came_from=(-1, 0))
    g = s.stub(s.pin(qp, "G"))
    # VGATE row: gate -> right; R440 up to +VDRV (joined with the P-FET source), R443 down to the reset divider
    s.wire(g, (g[0] + 27.94, g[1]))
    s.place_pin_at(rpu, 2, (g[0] + 15.24, g[1] - 2.54))
    s.wire((g[0] + 15.24, g[1]), s.pin(rpu, 2))
    top = s.pin(rpu, 1).out()
    s.wire(s.pin(rpu, 1), top)
    s.wire(so, (top[0], so[1]))
    s.wire((top[0], so[1]), top) if top[1] != so[1] else None
    s.power_at((top[0], min(top[1], so[1])), "+VDRV", came_from=(1, 0))
    s.place_pin_at(rrh, 1, (g[0] + 27.94, g[1] + 2.54))
    s.wire((g[0] + 27.94, g[1]), s.pin(rrh, 1))
    n = s.pin(rrh, 2).out()
    s.place_pin_at(rrl, 1, (n[0], n[1] + 2.54))
    s.wire(s.pin(rrh, 2), s.pin(rrl, 1))
    s.power(s.pin(rrl, 2))
    s.place_pin_at(qr, "G", (n[0] + 12.7, n[1]))
    s.wire(n, s.pin(qr, "G"))
    s.power(s.pin(qr, "S"))
    s.label(s.pin(qr, "D"))
    s.place_pin_at(qr2, "G", (n[0] + 35.56, n[1]))
    s.label(s.pin(qr2, "G"))
    s.power(s.pin(qr2, "S"))
    s.label(s.pin(qr2, "D"))
    s.place(d.by_ref("TP40"), n[0] + 55.88, n[1] - 10.16)
    # Q47 pulls VGATE low when its gate is high
    s.place_pin_at(qn, "D", (g[0], g[1] + 7.62))
    s.wire(g, s.pin(qn, "D"))
    s.power(s.pin(qn, "S"))
    gn = s.stub(s.pin(qn, "G"))
    s.place_pin_at(rens, 2, (gn[0], gn[1] - 2.54))
    s.wire(gn, s.pin(rens, 2))
    s.label(s.pin(rens, 1))
    s.place_pin_at(renpd, 1, (gn[0], gn[1] + 2.54))
    s.wire(gn, s.pin(renpd, 1))
    s.power(s.pin(renpd, 2))
    # Q48: ARM_N high (link open) shorts Q47's gate to ground
    s.place_pin_at(qi, "D", (gn[0] - 12.7, gn[1] + 2.54))
    s.wire(gn, (gn[0] - 12.7, gn[1]), s.pin(qi, "D"))
    s.power(s.pin(qi, "S"))
    s.label(s.pin(qi, "G"))


def draw_bridge(d, s: Sheet, k: str, base: int):
    vcc_name = "W_VCC" if k == "W" else "+VDRV"
    s.text(20, 25, f"ESC {k} power stage: 3× half-bridge HYG015N04LS1C2 (40 V, 2 mΩ), bootstrap 2.2 Ω + 1N5819WS + 100 nF, low-side 1 mΩ shunt", 2, True)
    s.text(20, 31, f"Gate drive from {vcc_name} (9–12.6 V).  Bulk: 2× 10 µF MLCC at the drains + 470 µF hybrid polymer (×2 on the weapon).  Motor pads A/B/C on J (2 mm holes + top lands).", 1.5)
    u = base // 10
    Y = 81.28
    bus_y = Y + 45.72
    for i, ph in enumerate("ABC"):
        X = 63.5 + i * 78.74
        qh, ql = d.by_ref(f"Q{u + i * 2}"), d.by_ref(f"Q{u + i * 2 + 1}")
        rgh, rgl = d.by_ref(f"R{base + 20 + i * 2}"), d.by_ref(f"R{base + 21 + i * 2}")
        rgsh, rgsl = d.by_ref(f"R{base + 26 + i * 2}"), d.by_ref(f"R{base + 27 + i * 2}")
        dbt, rbt, cbt = d.by_ref(f"D{u + i}"), d.by_ref(f"R{base + 32 + i}"), d.by_ref(f"C{base + 20 + i}")
        s.place(qh, X, Y)
        s.place(ql, X, Y + 22.86)
        s.power(s.pin(qh, "D"))
        # phase node
        hs, ld = s.pin(qh, "S"), s.pin(ql, "D")
        s.wire(hs, ld)
        mid = (hs.x, Y + 11.43)
        s.wire(mid, (mid[0] + 20.32, mid[1]))
        s.label_at((mid[0] + 20.32, mid[1]), f"MOTOR_{k}_{ph}", 0)
        # high-side gate
        gh = s.stub(s.pin(qh, "G"))
        s.place_pin_at(rgh, 2, (gh[0] - 2.54, gh[1]), 90)
        s.wire(gh, s.pin(rgh, 2))
        s.label(s.pin(rgh, 1))
        s.place_pin_at(rgsh, 1, (gh[0], gh[1] + 2.54))
        s.wire(gh, s.pin(rgsh, 1))
        s.wire(s.pin(rgsh, 2), (gh[0], mid[1]), mid)
        # low-side gate
        gl = s.stub(s.pin(ql, "G"))
        s.place_pin_at(rgl, 2, (gl[0] - 2.54, gl[1]), 90)
        s.wire(gl, s.pin(rgl, 2))
        s.label(s.pin(rgl, 1))
        s.place_pin_at(rgsl, 1, (gl[0], gl[1] + 2.54))
        s.wire(gl, s.pin(rgsl, 1))
        s.wire(s.pin(rgsl, 2), (gl[0], bus_y))  # gate-source: returns to the low-side source bus (I_x+)
        # bootstrap
        vb = (mid[0] + 10.16, Y - 5.08)
        s.place_pin_at(cbt, 2, (vb[0], mid[1] - 2.54))
        s.wire(s.pin(cbt, 2), (vb[0], mid[1]))
        s.wire(s.pin(cbt, 1), vb)
        s.wire(vb, (vb[0], vb[1] - 5.08))
        s.label_at((vb[0], vb[1] - 5.08), f"{k}_VB{i + 1}", 90)
        s.place_pin_at(dbt, "K", (vb[0] + 5.08, vb[1]), 0)
        s.wire(vb, s.pin(dbt, "K"))
        s.place_pin_at(rbt, 2, (s.pin(dbt, "A").out()[0] + 2.54, vb[1]), 90)
        s.wire(s.pin(dbt, "A"), s.pin(rbt, 2))
        s.power(s.pin(rbt, 1))
        # low-side source to the shunt bus
        so = s.stub(s.pin(ql, "S"))
        s.wire(so, (so[0], bus_y))
    s.wire((55.88, bus_y), (241.3, bus_y))
    rsh = d.by_ref(f"R{base + 35}")
    s.place_pin_at(rsh, 1, (241.3, bus_y + 2.54))
    s.wire((241.3, bus_y), s.pin(rsh, 1))
    gnd_pt = s.pin(rsh, 2).out()
    s.wire(s.pin(rsh, 2), gnd_pt)
    s.power_at(gnd_pt, "GND", up=False, came_from=(0, 1))
    ntp, ntm = d.by_ref(f"NT{u}"), d.by_ref(f"NT{u + 1}")
    s.place_pin_at(ntp, 1, (256.54, bus_y + 2.54), 90)     # pin 1 down onto I_x+, pin 2 up -> I_x_S+
    s.wire((241.3, bus_y), (256.54, bus_y), s.pin(ntp, 1))
    s.label(s.pin(ntp, 2))
    s.place_pin_at(ntm, 1, (256.54, gnd_pt[1] - 2.54), 270)  # pin 1 up onto the GND node, pin 2 down -> I_x_S-
    s.wire(gnd_pt, (256.54, gnd_pt[1]), s.pin(ntm, 1))
    s.label(s.pin(ntm, 2))
    s.place(d.by_ref(f"TP{u}3"), 218.44, bus_y - 7.62)
    s.wire(s.pin(d.by_ref(f"TP{u}3"), 1), (218.44, bus_y))
    s.text(150, bus_y + 12.7, "Kelvin: NT net-ties on the shunt pads; INA180 (this cell) + INA226 (log) sense from them", 1.27)
    # bulk caps and motor connector
    bulk_refs = [f"C{base + 23}", f"C{base + 24}", f"C{base + 25}"] + ([f"C{base + 26}"] if k == "W" else [])
    decap_strip(s, d, bulk_refs, 63.5, 185.42, "Bulk at the FET drains (VBAT): 2x 10 uF MLCC + hybrid polymer")
    j = d.by_ref(f"J{u + 1}")
    s.text(255, 175, f"Motor {k} pads", 1.5, True)
    s.place(j, 264.16, 185.42)
