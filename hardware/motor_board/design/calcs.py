#!/usr/bin/env python3
"""Motor-board design calculations.  Every number in DESIGN.md section 4 comes from here.

    python3 hardware/motor_board/design/calcs.py        (writes calcs.md next to this file)

Sources: DRV8316 SLVSF16B, DRV8323 SLVSDJ3D, LMR16006 SNVSA24, HYG015N04LS1C2 datasheet,
STM32G474 (12-bit ADC, VREF+ = 3.3 V), AP2112K datasheet.
"""
from math import pi, sqrt
from pathlib import Path

out = []


def h(t):
    out.append(f"\n## {t}\n")


def row(name, value, note=""):
    out.append(f"| {name} | {value} | {note} |")


def table(title):
    h(title)
    out.append("| Quantity | Value | Basis |")
    out.append("|---|---|---|")


VBAT_MAX, VBAT_NOM, VBAT_MIN = 16.8, 14.8, 12.0      # 4S full / nominal / sagged
VREF = 3.3
LSB = VREF / 4096

# ---------------------------------------------------------------- current sensing
table("1. Current sensing ranges")
for g in (0.15, 0.3, 0.6, 1.2):
    rng = (VREF / 2 - 0.25) / g          # linear range: SOx within 0.25 V of the rails
    row(f"Drive DRV8316 CSA gain {g} V/A", f"+-{rng:.1f} A, {LSB / g * 1000:.1f} mA/LSB",
        "SOx biased at VREF/2; linear to 0.25 V from the rails (SLVSF16B 7.5)" + ("  <- use (covers the 8 A peak)" if g == 0.15 else ""))
for rsh, g in ((0.002, 20), (0.002, 10), (0.001, 40)):
    rng = (VREF / 2 - 0.25) / (rsh * g)
    row(f"Weapon {rsh*1000:.0f} mOhm x {g} V/V", f"+-{rng:.0f} A, {LSB / (rsh * g) * 1000:.0f} mA/LSB",
        "bidirectional (VREF_DIV=1)" + ("  <- use: 20 A limit at 0.8 V, 1.5x headroom for fault detection" if (rsh, g) == (0.002, 20) else ""))
row("Weapon shunt loss at 20 A", f"{20**2*0.002:.2f} W peak per shunt", "2512 3 W part; RMS during spin-up (0.5 s) far lower")

# ---------------------------------------------------------------- voltage sensing
table("2. Voltage dividers (68k / 10k)")
k = 10 / 78
row("Ratio", f"{1/k:.2f}", "")
row("ADC at 16.8 V (4S full)", f"{16.8*k:.2f} V", "")
row("ADC at 25.2 V (6S full)", f"{25.2*k:.2f} V", "stays < 3.3 V, so the same board reads a 6S pack")
row("Resolution", f"{LSB/k*1000:.1f} mV/LSB", "")
row("Divider current at 16.8 V", f"{16.8/78e3*1e6:.0f} uA", "x4 dividers: ~0.9 mA total")

# ---------------------------------------------------------------- 5 V buck
table("3. 5 V buck (DRV8323R integrated LMR16006X, 0.7 MHz)")
fsw, vout, io = 0.7e6, 5.0, 0.6
for vin in (16.8, 25.2):
    lmin = (vin - vout) / (io * 0.4) * vout / (vin * fsw)
    row(f"L min at VIN {vin} V (ripple 40 %)", f"{lmin*1e6:.1f} uH", "SNVSA24 eq. 1 -> 22 uH standard")
L = 22e-6
for vin in (12.0, 16.8, 25.2):
    irip = vout * (vin - vout) / (vin * L * fsw)
    row(f"Ripple current at {vin} V, 22 uH", f"{irip*1000:.0f} mA p-p, peak {1000*(io+irip/2):.0f} mA", "inductor Isat >= 1.2 A (the LMR16006 current limit) recommended")
row("FB divider", f"0.765 x (1 + 56k/10k) = {0.765*(1+56/10):.2f} V", "VFB 0.747-0.782 V -> 4.93-5.16 V")
row("Cout min (3 % droop, 0.57 A step)", f"{2*0.57/(fsw*0.15)*1e6:.1f} uF", "SNVSA24 eq. 5 -> 2 x 22 uF 25 V (derates to ~2 x 10 uF at 5 V)")
row("Diode", "B5819W 40 V 1 A SOD-123", ">=1.25 x VIN max (21 V at 4S; 31.5 V at 6S)")
eff = 0.85
p5 = 5.0 * 0.45
row("Input power at 0.45 A out", f"{p5/eff:.2f} W ({p5/eff/VBAT_NOM*1000:.0f} mA from the pack)", "85 % assumed")

# ---------------------------------------------------------------- power budget
table("4. Logic power budget (5 V rail, 600 mA max)")
loads = [("STM32G474 at 170 MHz, all timers/ADCs", 0.080, "3V3"), ("3 x driver logic (DVDD/AVDD from VM, not 5 V)", 0.0, "-"),
         ("2 x MT6701 encoder", 0.024, "3V3"), ("CSA VREF (3 x ~2 mA)", 0.006, "3V3"), ("LED, pull-ups", 0.004, "3V3")]
i33 = sum(i for _, i, r in loads if r == "3V3")
for n, i, r in loads:
    row(n, f"{i*1000:.0f} mA", r)
row("3.3 V total", f"{i33*1000:.0f} mA", f"AP2112K from 5 V dissipates {(5-3.3)*i33*1000:.0f} mW")
row("Available for the compute board", f"{(0.6 - i33 - 0.03)*1000:.0f} mA at 5 V", "Pico W peak ~300 mA with Wi-Fi; IMUs/flash/LEDs ~100 mA")

# ---------------------------------------------------------------- drive thermal
table("5. Drive channel (DRV8316) thermal")
rds = 0.095
for i in (1.0, 2.0, 3.0, 4.0):
    p = 3 * i**2 * rds / 2          # 3 phases, each phase current through one ~47.5 mOhm FET at a time
    row(f"Phase current {i:.0f} A rms", f"{p:.2f} W conduction (+ ~0.1 W switching)", f"RthJA 25.7 C/W (JEDEC) -> +{p*25.7:.0f} C")
row("Guidance", "<= 2.5-3 A rms continuous per motor, 8 A peak", "real RthJA depends on copper; Repeat Mini class needs ~1 A running, 4 A limit")

# ---------------------------------------------------------------- weapon FETs
table("6. Weapon bridge (HYG015N04LS1C2, 1.4 mOhm @10 V)")
rds = 0.0014 * 1.5                  # hot
for i in (5.0, 10.0, 20.0):
    row(f"{i:.0f} A phase (rms)", f"{i**2*rds:.2f} W conduction per conducting FET", "RDS x1.5 for temperature")
qgd, qg = 8.5e-9, 59e-9
for idr in (0.06, 0.12, 0.26):
    t = qgd / idr
    psw = 0.5 * VBAT_MAX * 20 * 2 * t * 24e3
    row(f"IDRIVE {idr*1000:.0f} mA source", f"dV/dt edge {t*1e9:.0f} ns, switching loss {psw:.2f} W per switching FET at 20 A / 24 kHz", "Qgd 8.5 nC")
row("Charge pump budget", f"3 x Qg x f = {3*qg*24e3*1000:.1f} mA at 24 kHz", "DRV8323 VCP supplies 25 mA at VM >= 13 V: OK")
row("Recommendation", "IDRIVE ~60/120 mA (source/sink), loop <= 6 nH", "see spice/sim_weapon_bridge.py: 400 mA overshoots, 50-100 mA stays in limits")

# ---------------------------------------------------------------- battery & bulk
table("7. Battery current and bulk capacitor")
row("Weapon spin-up (20 A limit)", "22 A pack peak, bus sags to ~14.1 V, 0.52 s to 90 %", "spice/sim_weapon_spinup.py")
irms_cap = 0.6 * 20 / sqrt(2)
row("Bus-capacitor ripple current at 20 A phase peak", f"~{irms_cap:.0f} A rms (SVPWM, M~0.5)", "shared by C1 polymer and 4 x 10 uF MLCC; bursts < 1 s")
row("Why the 470 uF polymer is mandatory", "keeps VM dV/dt at plug-in < 2 V/us", "spice/sim_hotplug.py: MLCC-only gives 4.4-5.5 V/us (> DRV8316 4 V/us limit)")
row("XT30 on the pack lead", "15 A continuous / 30 A burst", "pack peak 22 A for 0.5 s is within the burst rating")

# ---------------------------------------------------------------- timers
table("8. Timer / sensor plan")
row("PWM", "24 kHz centre-aligned, TIM1 (weapon), TIM8 (drive L), TIM20 (drive R)", "3x PWM mode: drivers generate complementary + dead time")
row("Weapon INL (Hi-Z)", "TIM1_CH1N-3N", "timer-driven phase enables for six-step/coast; high for FOC")
row("Drive sensors", "TIM3 (L), TIM2 (R) CH1-3: Hall interface or encoder mode", "MT6701 ABZ up to 1024 PPR x4, or UVW Hall emulation")
enc_counts = 1024 * 4 * 28.5
row("Odometry resolution (MT6701 1024 PPR on motor, 28.5:1)", f"{enc_counts:.0f} counts/wheel rev = {pi*43.2/enc_counts*1000:.2f} um", "43.2 mm wheel")
hall_counts = 6 * 2 * 28.5
row("Odometry resolution (Halls, 2 pole pairs, 28.5:1)", f"{hall_counts:.0f} counts/wheel rev = {pi*43.2/hall_counts:.2f} mm", "")


# ---------------------------------------------------------------- battery monitoring / power entry
table("9. Pack monitoring and power entry")
row("INA229 range with 1 mOhm (ADCRANGE=1, +-40.96 mV)", "+-41 A", "pack peak 22-27 A during spin-up")
row("INA229 current resolution", f"{40.96e-3/2**19/0.001*1e6:.0f} uA/LSB (20-bit)", "energy (J) and charge (C) accumulate in hardware: mAh used per match")
row("Pack shunt loss", f"{0.001*22**2:.2f} W at 22 A, {0.001*5**2*1000:.0f} mW at 5 A", "RS4 1 mOhm 2512 3 W")
row("RPP FET (Q7) loss", f"{0.0014*1.5*22**2:.2f} W at 22 A (hot RDS)", "vs ~0.5 V x 22 A = 11 W for a Schottky; zener bias 48 uA at 16.8 V")
# buck UVLO: node equation with SHDN pull-up current 1 uA below / 4.2 uA above threshold (SNVSA24 7.5)
r1, r2 = 390e3, 51e3
for vth in (1.05, 1.25, 1.38):
    rise = r1 * (vth / r2 - 1e-6) + vth
    fall = r1 * (vth / r2 - 4.2e-6) + vth
    row(f"Buck UVLO at SHDN threshold {vth} V", f"on {rise:.1f} V / off {fall:.1f} V", "390 k / 51 k; typ = 1.25 V" if vth == 1.25 else "datasheet min/max threshold")
row("UVLO vs weapon sag", "off <= 10.3 V worst case vs 13.7 V minimum bus during a 25 A spin-up", "margin for a tired pack; firmware warns long before (3.5 V/cell)")
row("Drain with the buck off (left plugged in)", "~0.9 mA (4 x 68k/10k dividers) + driver sleep currents", "the few % of capacity left below the cutoff lasts ~1-2 days: unplug the pack after use")

text = "# Motor board design calculations (generated by calcs.py - do not edit)\n" + "\n".join(out) + "\n"
Path(__file__).with_name("calcs.md").write_text(text)
print(text)
