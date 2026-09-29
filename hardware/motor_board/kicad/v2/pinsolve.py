"""MCU pin co-assignment for the v2 floorplan (CP-SAT).  Keeps the firmware architecture of DESIGN 3.4 (timers, ADC
sampling plan, comparator trips, SPI/USART) but lets every function move to any legal pin, lets the instance choices
float where the architecture allows it, and minimises pin-to-destination geometry for a given MCU placement.
    uv run --no-project --with ortools python pinsolve.py [x y rot]   (rot = KiCad footprint orientation, deg)
Writes out/pinsolve_<rot>.json.  Pin legality comes from ref/STM32G474RxTx_pins.xml only.

Architecture kept (DESIGN 3.4 / 8):
  weapon  TIM1 CHk + CHkN per phase (INH direct, INL via U6); W_nFAULT on TIM1_BKIN/BKIN2
  drives  TIM8 and TIM20 (one each, either way), CH1-3 in any order; nFAULT on its timer's BKIN if possible, else GPIO
  sensors two of TIM2/3/4/5, S1/S2 on CH1/CH2 (encoder A/B, either order), S3 on CH3
  weapon CSA  one phase on ADC1 and ADC2, one on ADC2 only-role, one on ADC1-role; each on its own COMPx_INP
  drive CSA   one drive "ADC5 mode" (two phases on ADC5_IN1/IN2 = PA8/PA9, third on an OPAMP5_VINP pin),
              the other "ADC3/4 mode" (one phase on ADC4, two on ADC3)
  regular ADC W_VA/B/C, VBAT_SNS, W_NTC, L/R_MTEMP each on ADC1 or ADC2; at least one phase voltage on each;
              ADC1 <= 3 (VREFINT is the 4th), ADC2 <= 4
  SPI1/2/3 for the shared bus, any USART/UART/LPUART for MB_TX/RX, SWD PA13/PA14, NRST pin 7
Reset-state rules (memo 3.3): PA15/PB4 JTAG pull-ups: no PWM output or W_EN; PB4/PB6 UCPD dead-battery pull-downs:
no chip select, DRV_OFF or nFAULT; PB8-BOOT0 only for a chip select (pull-up); PC13-15 only for slow signals."""
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent
MB = HERE.parents[1]
MCU = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (40.0, 26.75)
ROT = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

# ------------------------------------------------------------------ pins and their signals
ns = {"n": "http://dummy.com"}
root = ET.parse(MB / "ref" / "STM32G474RxTx_pins.xml").getroot()
PIN = {}
for p in root.findall("n:Pin", ns):
    if p.get("Type") != "I/O":
        continue
    PIN[p.get("Position")] = (p.get("Name"), {s.get("Name") for s in p.findall("n:Signal", ns)})
FIXED = {"NRST": "7", "SWDIO": "49", "SWCLK": "50"}


def pin_xy(pin):
    """pad centre of LQFP-64 pin in board coordinates: KiCad footprint (pin 1 top-left, CCW), rotated by ROT
    (KiCad: positive = counter-clockwise on screen, y down), placed at MCU."""
    n = int(pin) - 1
    side, k = divmod(n, 16)
    off = -3.75 + 0.5 * k
    x, y = [(-5.75, off), (off, 5.75), (5.75, -off), (-off, -5.75)][side]
    a = math.radians(ROT)
    xr = x * math.cos(a) + y * math.sin(a)
    yr = -x * math.sin(a) + y * math.cos(a)
    return MCU[0] + xr, MCU[1] + yr, (x, y)


# destination anchors (floorplan variant A, top view, mm)
A = {"U3": (8, 24), "U4": (23, 25), "SENL": (7, 31), "SENR": (22, 31), "U2": (56, 23), "AND": (54, 25),
     "J1": (73, 23), "ARM": (70, 25), "INA": (36, 10), "PDIV": (63, 10), "BRIDGE": (63, 12), "TPS": (54, 31)}
DEST = {
    "W_INHA": ["U2"], "W_INHB": ["U2"], "W_INHC": ["U2"], "W_INLA_M": ["AND"], "W_INLB_M": ["AND"], "W_INLC_M": ["AND"],
    "W_nFAULT": ["U2", "INA"], "W_EN": ["U2", "J1"], "W_ARM_S": ["ARM", "AND"],
    "W_SOA": ["U2"], "W_SOB": ["U2"], "W_SOC": ["U2"],
    "W_VA": ["PDIV"], "W_VB": ["PDIV"], "W_VC": ["PDIV"], "W_NTC": ["BRIDGE"], "VBAT_SNS": ["J1", "INA"],
    "L_INHA": ["U3"], "L_INHB": ["U3"], "L_INHC": ["U3"], "L_nFAULT": ["U3"], "L_nCS": ["U3"],
    "R_INHA": ["U4"], "R_INHB": ["U4"], "R_INHC": ["U4"], "R_nFAULT": ["U4"], "R_nCS": ["U4"],
    "L_SOA_F": ["U3"], "L_SOB_F": ["U3"], "L_SOC_F": ["U3"], "R_SOA_F": ["U4"], "R_SOB_F": ["U4"], "R_SOC_F": ["U4"],
    "L_S1": ["SENL"], "L_S2": ["SENL"], "L_S3": ["SENL"], "L_MTEMP": ["SENL"],
    "R_S1": ["SENR"], "R_S2": ["SENR"], "R_S3": ["SENR"], "R_MTEMP": ["SENR"],
    "DRV_OFF": ["U3", "U4"], "SPI_SCK": ["U3", "U4", "INA"], "SPI_MISO": ["U3", "U4", "INA"], "SPI_MOSI": ["U3", "U4", "INA"],
    "INA_nCS": ["INA"], "MB_TX": ["J1"], "MB_RX": ["J1"], "NRST": ["J1"], "SWDIO": ["J1"], "SWCLK": ["J1"],
}


GEOM = None
if "--geom" in sys.argv:
    # destinations from the real placement (render.py dump): every other pad on the net; the CSA filter nets (_F)
    # use their source net (the DRV8316 SOx pin), since the filter sits at the MCU pin
    import json as _json
    GEOM = _json.load(open(sys.argv[sys.argv.index("--geom") + 1]))
    _pads = {}
    for p in GEOM["pads"]:
        if p["ref"] != "U1":
            _pads.setdefault(p["net"].split("/")[-1], []).append(tuple(p["c"]))
    DESTPTS = {}
    for n in DEST:
        src = n[:-2] if n.endswith("_F") else n
        pts = _pads.get(src, [])
        if n.endswith("_F"):
            pts = [q for q in pts if math.dist(q, MCU) > 9.0]   # the DRV8316 pin, not the filter resistor
        DESTPTS[n] = pts or [A[d] for d in DEST[n]]


def cost(net, pin):
    px, py, (lx, ly) = pin_xy(pin)
    pts = DESTPTS[net] if GEOM else [A[d] for d in DEST[net]]
    c = 0.0
    for dx, dy in pts:
        # outward normal of the pin's edge (rotated)
        if abs(lx) > abs(ly):
            nx, ny = math.copysign(1, lx), 0.0
        else:
            nx, ny = 0.0, math.copysign(1, ly)
        a = math.radians(ROT)
        onx, ony = nx * math.cos(a) + ny * math.sin(a), -nx * math.sin(a) + ny * math.cos(a)
        bx, by = dx - px, dy - py
        d = math.hypot(bx, by)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (onx * bx + ony * by) / d))))
        c += abs(bx) + abs(by) + 0.12 * ang + (8.0 if ang > 100 else 0.0)
    return c / len(pts)


m = cp_model.CpModel()
opts = {}   # (net, pin, tag) -> BoolVar
def opt(net, pin, tag=""):
    k = (net, pin, tag)
    if k not in opts:
        opts[k] = m.NewBoolVar(f"{net}@{pin}{tag}")
    return opts[k]


def has(pin, sig):
    return sig in PIN[pin][1]


def pname(pin):
    return PIN[pin][0].split("-")[0]


PWM_BAD = {"PA15", "PB4", "PA13", "PA14"}      # reset pull-ups/JTAG: no gate-drive outputs
DB = {"PB4", "PB6"}                              # UCPD dead-battery pull-downs
SLOW = {"PC13", "PC14", "PC15"}
USABLE = [p for p in PIN if p not in FIXED.values()]

# ---- weapon TIM1: phase -> channel k (1..3), INH on CHk, INL_M on CHkN
wch = {(ph, k): m.NewBoolVar(f"w{ph}{k}") for ph in "ABC" for k in (1, 2, 3)}
for ph in "ABC":
    m.AddExactlyOne(wch[ph, k] for k in (1, 2, 3))
for k in (1, 2, 3):
    m.AddExactlyOne(wch[ph, k] for ph in "ABC")
for ph in "ABC":
    for k in (1, 2, 3):
        for p in USABLE:
            if pname(p) in PWM_BAD | SLOW:
                continue
            if has(p, f"TIM1_CH{k}"):
                m.AddImplication(opt(f"W_INH{ph}", p, f"k{k}"), wch[ph, k])
            if has(p, f"TIM1_CH{k}N"):
                m.AddImplication(opt(f"W_INL{ph}_M", p, f"k{k}"), wch[ph, k])
for p in USABLE:
    if has(p, "TIM1_BKIN"):          # BKIN, not BKIN2: break2 can only force the inactive level (RM0440 Table 260)
        opt("W_nFAULT", p, "bk")

# ---- drives: timer per drive (TIM8/TIM20), channels any order
DRV_T = (8, 20, 2, 3, 4, 5) if "--gp" in sys.argv else (8, 20)
dt = {(d, t): m.NewBoolVar(f"{d}{t}") for d in "LR" for t in DRV_T}
for d in "LR":
    m.AddExactlyOne(dt[d, t] for t in DRV_T)
for t in DRV_T:
    m.AddAtMostOne(dt[d, t] for d in "LR")
m.Add(sum(dt[d, t] for d in "LR" for t in (8, 20)) >= 1)   # TIM8_TRGO2 triggers the injected ADC groups
dch = {}
for d in "LR":
    for ph in "ABC":
        for k in (1, 2, 3):
            dch[d, ph, k] = m.NewBoolVar(f"{d}{ph}c{k}")
        m.AddExactlyOne(dch[d, ph, k] for k in (1, 2, 3))
    for k in (1, 2, 3):
        m.AddExactlyOne(dch[d, ph, k] for ph in "ABC")
    for ph in "ABC":
        for p in USABLE:
            if pname(p) in PWM_BAD | SLOW:
                continue
            for t in DRV_T:
                for k in (1, 2, 3):
                    if has(p, f"TIM{t}_CH{k}"):
                        v = opt(f"{d}_INH{ph}", p, f"t{t}k{k}")
                        m.AddImplication(v, dt[d, t])
                        m.AddImplication(v, dch[d, ph, k])
    for p in USABLE:
        if pname(p) in DB:
            continue
        for t in (8, 20):
            if has(p, f"TIM{t}_BKIN"):
                m.AddImplication(opt(f"{d}_nFAULT", p, f"bk{t}"), dt[d, t])
        opt(f"{d}_nFAULT", p, "gpio")

# ---- sensors: two of TIM2/3/4/5
GP = (2, 3, 4, 5)
st = {(d, t): m.NewBoolVar(f"s{d}{t}") for d in "LR" for t in GP}
for d in "LR":
    m.AddExactlyOne(st[d, t] for t in GP)
for t in GP:
    m.AddAtMostOne([st[d, t] for d in "LR"] + [dt[d, t] for d in "LR" if (d, t) in dt])
for d in "LR":
    for p in USABLE:
        for t in GP:
            for net, chans in ((f"{d}_S1", (1, 2)), (f"{d}_S2", (1, 2)), (f"{d}_S3", (3,))):
                for k in chans:
                    if has(p, f"TIM{t}_CH{k}"):
                        v = opt(net, p, f"t{t}k{k}")
                        m.AddImplication(v, st[d, t])
    # S1 and S2 on different channels of the same timer
    for t in GP:
        for k in (1, 2):
            m.AddAtMostOne([v for (n, p, tag), v in opts.items() if n in (f"{d}_S1", f"{d}_S2") and tag == f"t{t}k{k}"])

# ---- weapon CSA roles: role 'both' (ADC1+ADC2), 'a2' (ADC2), 'a1' (ADC1); each phase one role, each on a COMP
wrole = {(ph, r): m.NewBoolVar(f"wr{ph}{r}") for ph in "ABC" for r in ("both", "a1", "a2")}
for ph in "ABC":
    m.AddExactlyOne(wrole[ph, r] for r in ("both", "a1", "a2"))
for r in ("both", "a1", "a2"):
    m.AddExactlyOne(wrole[ph, r] for ph in "ABC")
comp_used = {}
for ph in "ABC":
    for p in USABLE:
        adc1 = any(re.fullmatch(r"ADC1_IN\d+", s) for s in PIN[p][1])
        adc2 = any(re.fullmatch(r"ADC2_IN\d+", s) for s in PIN[p][1])
        comps = sorted({int(re.match(r"COMP(\d)_INP", s).group(1)) for s in PIN[p][1] if re.match(r"COMP\d_INP", s)})
        for r, ok in (("both", adc1 and adc2), ("a1", adc1), ("a2", adc2)):
            if not ok:
                continue
            for c in comps:
                v = opt(f"W_SO{ph}", p, f"{r}c{c}")
                m.AddImplication(v, wrole[ph, r])
                comp_used.setdefault(c, []).append(v)
for c, vs in comp_used.items():
    m.AddAtMostOne(vs)

# ---- drive CSA modes
d5 = {d: m.NewBoolVar(f"adc5_{d}") for d in "LR"}
m.AddExactlyOne(d5.values())
for d in "LR":
    for ph in "ABC":
        net = f"{d}_SO{ph}_F"
        for p in USABLE:
            s = PIN[p][1]
            if "ADC5_IN1" in s or "ADC5_IN2" in s:
                m.AddImplication(opt(net, p, "adc5"), d5[d])
            if "OPAMP5_VINP" in s:
                m.AddImplication(opt(net, p, "op5"), d5[d])
            if any(re.fullmatch(r"ADC4_IN\d+", x) for x in s):
                m.AddImplication(opt(net, p, "adc4"), d5[d].Not())
            if any(re.fullmatch(r"ADC3_IN\d+", x) for x in s):
                m.AddImplication(opt(net, p, "adc3"), d5[d].Not())
    tag_vars = lambda tag: [v for (n, p, t), v in opts.items() if n.startswith(f"{d}_SO") and t == tag]
    # ADC5 mode: exactly 2 on ADC5 pins + 1 on OPAMP5; ADC3/4 mode: 1 on ADC4 + 2 on ADC3
    m.Add(sum(tag_vars("adc5")) == 2 * d5[d])
    m.Add(sum(tag_vars("op5")) == d5[d])
    m.Add(sum(tag_vars("adc4")) == 1 - d5[d])
    m.Add(sum(tag_vars("adc3")) == 2 - 2 * d5[d])

# ---- regular ADC1/ADC2 channels
REG = ["W_VA", "W_VB", "W_VC", "VBAT_SNS", "W_NTC", "L_MTEMP", "R_MTEMP"]
for net in REG:
    for p in USABLE:
        for a in (1, 2):
            if any(re.fullmatch(fr"ADC{a}_IN\d+", s) for s in PIN[p][1]):
                opt(net, p, f"a{a}")
reg = lambda a, nets=REG: [v for (n, p, t), v in opts.items() if n in nets and t == f"a{a}"]
m.Add(sum(reg(1)) <= 3)
m.Add(sum(reg(2)) <= 4)
m.Add(sum(reg(1, ["W_VA", "W_VB", "W_VC"])) >= 1)
m.Add(sum(reg(2, ["W_VA", "W_VB", "W_VC"])) >= 1)

# ---- SPI, USART
spi = {i: m.NewBoolVar(f"spi{i}") for i in (1, 2, 3)}
m.AddExactlyOne(spi.values())
for p in USABLE:
    for i in (1, 2, 3):
        for net, f in (("SPI_SCK", "SCK"), ("SPI_MISO", "MISO"), ("SPI_MOSI", "MOSI")):
            if has(p, f"SPI{i}_{f}"):
                m.AddImplication(opt(net, p, f"s{i}"), spi[i])
UARTS = ["USART1", "USART2", "USART3", "UART4", "UART5", "LPUART1"]
ua = {u: m.NewBoolVar(u) for u in UARTS}
m.AddExactlyOne(ua.values())
for p in USABLE:
    for u in UARTS:
        for net, f in (("MB_TX", "TX"), ("MB_RX", "RX")):
            if has(p, f"{u}_{f}"):
                m.AddImplication(opt(net, p, u), ua[u])

# ---- plain GPIOs
for net in ("L_nCS", "R_nCS", "INA_nCS"):
    for p in USABLE:
        if pname(p) in DB | SLOW | {"PA14"}:
            continue
        opt(net, p, "gpio")
for p in USABLE:
    if pname(p) not in DB | {"PA14"}:
        opt("DRV_OFF", p, "gpio")
    if pname(p) not in {"PA15", "PB4", "PB8", "PA13"}:
        opt("W_EN", p, "gpio")
    opt("W_ARM_S", p, "gpio")
for net, p in FIXED.items():
    opt(net, p, "fixed")

# ---- pin I/O structure (DS12288 Table 12, out/io_types.json): cable-exposed motor-NTC inputs on 5 V-tolerant pins
import json as _j
IO = _j.load(open(Path(__file__).resolve().parent / "out" / "io_types.json"))
IO.update({"PA9": "FT_da", "PA10": "FT_da", "PF0": "FT_fa", "PF1": "FT_a", "PC14": "FT", "PC15": "FT", "PB8": "FT_f"})
for (n, p, t_), v in list(opts.items()):
    if n in ("L_MTEMP", "R_MTEMP") and IO.get(pname(p), "TT").startswith("TT"):
        m.Add(v == 0)
# ---- EXTI: one port per line; these inputs need an interrupt
EXTI_NETS = ("W_ARM_S", "L_nFAULT", "R_nFAULT")
for line in range(16):
    vs = [v for (n, p, t_), v in opts.items() if n in EXTI_NETS and (t_ == "gpio" or n == "W_ARM_S")
          and int(re.sub(r"\D", "", pname(p)) or -1) == line]
    if len(vs) > 1:
        m.AddAtMostOne(vs)

# ---- PB8-BOOT0: chip selects only
for (n, p, t), v in list(opts.items()):
    if pname(p) == "PB8" and n not in ("L_nCS", "R_nCS", "INA_nCS"):
        m.Add(v == 0)
# and PB8 must carry one of them: its pull-up (DRV8316 nSCS internal, or R12 on INA_nCS) sets BOOT0 through reset
# (a blank chip boots the ROM loader; SWD programming does not care); the pin must not float (DS12288 is silent on
# an internal pull)
m.AddExactlyOne(v for (n, p, t), v in opts.items() if pname(p) == "PB8")

# ---- one option per net, one net per pin
nets = sorted({n for (n, p, t) in opts})
missing = set(DEST) - set(nets)
assert not missing, missing
for net in nets:
    m.AddExactlyOne(v for (n, p, t), v in opts.items() if n == net)
for p in PIN:
    m.AddAtMostOne(v for (n, pp, t), v in opts.items() if pp == p)

# objective (+ prefer drive nFAULT on its BKIN)
terms = []
for (n, p, t), v in opts.items():
    c = cost(n, p)
    if n in ("L_nFAULT", "R_nFAULT") and t == "gpio":
        c += 6.0
    if n in ("W_VA", "W_VB", "W_VC", "VBAT_SNS") and IO.get(pname(p), "TT").startswith("TT"):
        c += 15.0                    # TVS-level spikes: prefer a 5 V-tolerant analog pin (DESIGN 7.4)
    terms.append(int(round(c * 10)) * v)
# general-purpose timer on a drive: firmware change (no BKIN, not TIM8/TIM20), penalised
for (d, tt), v in dt.items():
    if tt not in (8, 20):
        terms.append(150 * v)
# UART pair on one edge
edge = lambda p: (int(p) - 1) // 16
for (n1, p1, t1), v1 in opts.items():
    if n1 != "MB_TX":
        continue
    for (n2, p2, t2), v2 in opts.items():
        if n2 == "MB_RX" and edge(p1) != edge(p2):
            b = m.NewBoolVar("")
            m.AddBoolAnd([v1, v2]).OnlyEnforceIf(b)
            m.AddBoolOr([v1.Not(), v2.Not()]).OnlyEnforceIf(b.Not())
            terms.append(100 * b)
m.Minimize(sum(terms))
sol = cp_model.CpSolver()
sol.parameters.max_time_in_seconds = 60
sol.parameters.num_workers = 8
r = sol.Solve(m)
print("status", sol.StatusName(r), "objective", sol.ObjectiveValue() / 10)
out = {}
for (n, p, t), v in sorted(opts.items(), key=lambda kv: int(kv[0][1])):
    if sol.Value(v):
        out[n] = dict(pin=p, port=PIN[p][0], tag=t, cost=round(cost(n, p), 1))
side_of = lambda p: "LBRT"[(int(p) - 1) // 16]
for n, d in sorted(out.items(), key=lambda kv: int(kv[1]["pin"])):
    print(f"{d['pin']:>3s} {d['port']:10s} {side_of(d['pin'])} {n:10s} {d['tag']:8s} {d['cost']:5.1f}")
print("drive timers:", {d: t for (d, t), v in dt.items() if sol.Value(v)}, " sensor timers:",
      {d: t for (d, t), v in st.items() if sol.Value(v)}, " ADC5 drive:", [d for d in "LR" if sol.Value(d5[d])],
      " SPI:", [i for i in spi if sol.Value(spi[i])], " UART:", [u for u in ua if sol.Value(ua[u])])
json.dump(dict(mcu=MCU, rot=ROT, pins=out), open(HERE / "out" / f"pinsolve_{int(ROT)}.json", "w"), indent=1)
