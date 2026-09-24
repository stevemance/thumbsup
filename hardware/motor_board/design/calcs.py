#!/usr/bin/env python3
"""Motor-board design calculations.  Every number in DESIGN.md section 4 comes from here.

    python3 hardware/motor_board/design/calcs.py        (writes calcs.md next to this file)

Sources: DRV8316C SLVSH07, DRV8323RH SLVSDJ3D, LMR16006 SNVSA24, HYG015N04LS1C2 datasheet,
STM32G474 (12-bit ADC, VREF+ = 3.3 V), AP2112K, INA239 SBOSA22, TPS22945 SLVS832D datasheets.
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
    lo, hi = (3.1 / 2 - 0.25) / g, (3.465 / 2 - 0.25) / g   # VREF = own AVDD, 3.1-3.465 V
    row(f"Drive DRV8316 CSA gain {g} V/A", f"+-{rng:.1f} A (+-{lo:.1f}..{hi:.1f} A over AVDD), {LSB / g * 1000:.1f} mA/LSB",
        "SOx biased at VREF/2; linear to 0.25 V from the rails (SLVSH07 7.5)" + ("  <- use (covers the 8 A peak)" if g == 0.15 else ""))
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
    row(f"Ripple current at {vin} V, 22 uH", f"{irip*1000:.0f} mA p-p, peak {1000*(io+irip/2):.0f} mA", "inductor Isat >= 1.6 A (TI SNVSA24 9.2.2.2; current limit 1.2 typ / 1.7 max A)")
row("FB divider", f"0.765 x (1 + 56k/10k) = {0.765*(1+56/10):.2f} V", "VFB 0.747-0.782 V -> 4.93-5.16 V")
row("Cout min (3 % droop, 0.57 A step)", f"{2*0.57/(fsw*0.15)*1e6:.1f} uF", "SNVSA24 eq. 5 -> 2 x 22 uF 25 V (derates to ~2 x 10 uF at 5 V)")
row("Inductor", "FNR5040S220MT: 22 uH, Isat 1.6 A guaranteed / 1.8 A typ (-30 % L), DCR 0.17 max, 5 x 5 mm",
    "meets TI's 1.6 A recommendation (SNVSA24 9.2.2.2); only a hard +5V short (current limit 1.2 typ / 1.7 max A) reaches soft ferrite roll-off")
row("Diode", "SS34 40 V 3 A SMA", ">=1.25 x VIN max; carries ~ILIMIT (<= 1.7 A) almost continuously into a shorted output")
eff = 0.85
p5 = 5.0 * 0.45
row("Input power at 0.45 A out", f"{p5/eff:.2f} W ({p5/eff/VBAT_NOM*1000:.0f} mA from the pack)", "85 % assumed")

# ---------------------------------------------------------------- power budget
table("4. Logic power budget (5 V rail, 600 mA max)")
loads = [("STM32G474 at 170 MHz, all timers/ADCs", 0.080, "3V3"), ("3 x driver logic (DVDD/AVDD from VM, not 5 V)", 0.0, "-"),
         ("2 x MT6701 encoder (or 6 Hall ICs)", 0.030, "3V3"), ("CSA VREF (U2)", 0.002, "3V3"),
         ("INA239, BQ76907 (from BAT), logic (U6, U9, U10, U11, U12, U14)", 0.002, "3V3"),
         ("Sensor pull-ups 6 x 4.7k (all low), NTC/fault pull-ups", 0.006, "3V3")]
i33 = sum(i for _, i, r in loads if r == "3V3")
for n, i, r in loads:
    row(n, f"{i*1000:.0f} mA", r)
row("3.3 V total", f"{i33*1000:.0f} mA", f"AP2112K from 5 V dissipates {(5-3.3)*i33*1000:.0f} mW")
row("Available for the compute board", f"{(0.6 - i33 - 0.03)*1000:.0f} mA at 5 V", "Pico W peak ~300 mA with Wi-Fi; IMUs/flash/LEDs ~100 mA")

# ---------------------------------------------------------------- drive thermal
table("5. Drive channel (DRV8316C) thermal")
# SLVSH07 7.5: RDS(on) HS+LS at 150 C 140 typ / 185 max mOhm; SLEW 11b 110/200/280 V/us (20-80 %); tDEAD 500/750 ns
# at 200 V/us; IVM 11/16 mA at 25 kHz (19/22 at 200 kHz; ~16 mA assumed at 48 kHz) with BUCK_DIS = 1.
# 3 phases, |i| avg ~0.9 x rms, drive PWM 48 kHz (see section 10: 6 pole pairs at up to 5.9 kHz electrical).
def drv_loss(i, rds, sr, tdead, fpwm=48e3):
    pc = 3 * i**2 * rds / 2
    t_edge = VBAT_MAX / (0.6 * sr)                        # full edge from a 20-80 % slew spec
    psw = 3 * 0.5 * VBAT_MAX * (0.9 * i) * 2 * t_edge * fpwm
    pdt = 3 * 2 * tdead * fpwm * 0.8 * (0.9 * i)          # body diode during dead time, VF ~0.8 V
    pq = VBAT_MAX * 0.016
    return pc, psw, pdt, pq
for i in (1.0, 1.5, 2.0, 3.0):
    pc, psw, pdt, pq = drv_loss(i, 0.140, 200e6, 0.5e-6)
    p = pc + psw + pdt + pq
    pcm, pswm, pdtm, pqm = drv_loss(i, 0.185, 110e6, 0.75e-6)
    pm = pcm + pswm + pdtm + pqm
    row(f"Phase current {i:.1f} A rms", f"typ {p:.2f} W (cond {pc:.2f} + sw {psw:.2f} + dead-time {pdt:.2f} + quiescent {pq:.2f}); worst {pm:.2f} W",
        f"RthJA 25.7 C/W (JEDEC) -> +{p*25.7:.0f} C typ / +{pm*25.7:.0f} C worst")
row("Guidance", "<= 2 A rms continuous per motor at 48 kHz; the Mk4.1 is traction-limited at ~1-1.5 A (section 10)",
    "OTW 135 C min, OTSD 165 C min; the board's real RthJA is worse than JEDEC.  Firmware enables OTW reporting and derates")

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
row("Chosen (DRV8323RH strap)", "IDRIVE 75k to AGND = 60/120 mA (source/sink), loop <= 6 nH", "see spice/sim_weapon_bridge.py: 400 mA overshoots, 50-100 mA stays in limits")
for r_on, tag in ((0.0014, "cold typ"), (0.0017, "cold max"), (0.0014 * 1.5, "hot")):
    row(f"VDS OCP trip (18k to AGND = 0.13 V), {tag}", f"{0.13 / r_on:.0f} A", "hard-short / shoot-through backstop only; below it the MCU limits phase current (FOC limit + comparator fast trip on all three CSAs)")

# ---------------------------------------------------------------- battery & bulk
table("7. Battery current and bulk capacitor")
row("Weapon spin-up (20 A limit)", "22 A pack peak, bus sags to ~14.1 V, 0.52 s to 90 %", "spice/sim_weapon_spinup.py")
irms_cap = 0.6 * 20 / sqrt(2)
row("Bus-capacitor ripple current at 20 A phase peak", f"~{irms_cap:.0f} A rms (SVPWM, M~0.5)", "shared by C1 polymer and the weapon MLCCs C25/C26/C31; bursts < 1 s")
row("Switch-closure VM ramp (DRV8316 abs max 4 V/us)", "<= 0.01 V/us with the U13/Q7/Q8 soft-start (see section 9)",
    "without a limiter the ramp is set by C1 ESR x dI/dt: a stiff pack, short leads or an aged/cold C1 exceed 4 V/us (round-2 simulation)")
row("DRV8316 VM filter (R302/R402 0.1 ohm 1 W + 4 x 10 uF ~16 uF)", "RC ~1.6 us (corner ~99 kHz, above the 48 kHz PWM); 0.11/0.24/0.52 W at 1/1.5/2 A rms incl. PWM ripple, <= ~1 W in weapon bursts; 0.8 V drop at 8 A",
    "spice/sim_hotplug.py: every switch/bounce event <= 2.75 V/us at the VM pins in the 0-50 C environment (loaded bounce, re-close; 2.82 V/us only with C1 at its -40 C ESR and a ~1.3 ms bounce); weapon fault-clear kick ~1-2 V/us (review round 10 sims)")
row("C1 voltage rating", "35 V vs SMBJ20A clamp 32.4 V max", "the TVS protects the capacitor, not the other way round")
row("XT30 on the pack lead", "15 A continuous / 30 A burst", "pack peak 22 A for 0.5 s is within the burst rating")

# ---------------------------------------------------------------- timers
table("8. Timer / sensor plan")
row("PWM", "TIM1 (weapon) 24 kHz; TIM8 (drive L) and TIM20 (drive R) 48 kHz, synchronised to TIM1", "3x PWM mode: drivers generate complementary + dead time; ADC injected trigger TIM8_TRGO2 (OC6REF) at 48 kHz, drives in PWM mode 2")
row("Weapon INL (Hi-Z)", "TIM1_CH1N-3N", "timer-driven phase enables for six-step/coast; high for FOC")
row("Drive sensors", "TIM3 (L), TIM2 (R) CH1-3: Hall interface or encoder mode", "MT6701 ABZ up to 1024 PPR x4, or UVW Hall emulation")
enc_counts = 1024 * 4 * 28.5
row("Odometry resolution (MT6701 1024 PPR on motor, 28.5:1)", f"{enc_counts:.0f} counts/wheel rev = {pi*43.2/enc_counts*1000:.2f} um", "43.2 mm wheel")
hall_counts = 6 * 6 * 28.5
row("Odometry resolution (Halls, 6 pole pairs, 28.5:1)", f"{hall_counts:.0f} counts/wheel rev = {pi*43.2/hall_counts:.2f} mm", "only if a Hall-equipped motor is used")


# ---------------------------------------------------------------- battery monitoring / power entry
table("9. Pack monitoring and power entry")
row("INA239 range with 1 mOhm (ADCRANGE=1, +-40.96 mV)", "+-41 A", "pack peak 22-27 A during spin-up")
row("INA239 current resolution", f"{40.96e-3/2**15/0.001*1000:.2f} mA/LSB (16-bit)", "mAh per match integrated in firmware (INA229 drop-in: 20-bit + hardware energy/charge)")
row("Pack shunt loss", f"{0.001*22**2:.2f} W at 22 A, {0.001*5**2*1000:.0f} mW at 5 A", "RS4 1 mOhm 2512 3 W")
row("Switch FETs (Q7 + Q8) loss", f"{2*0.0014*1.5*22**2:.2f} W typ-hot / {2*0.0017*1.5*22**2:.2f} W max-hot at 22 A", "0.5 s bursts; vs ~0.5 V x 22 A = 11 W for a Schottky")
row("Soft-start (U13 LM74502, Cdvdt 22 nF, R32 1M bleed)", f"~2.2 V/ms ramp (sim; 1.3 V/ms at the 40 uA min, 3.0 V/ms at the 77 uA max gate current), ~{2.2e3*380e-6:.1f} A into ~380 uF",
    "spice/sim_hotplug.py: <= 0.01 V/us peak at VM, Q7 16 W peak (22.0 W at the max gate current) / 54-57 mJ per closure; >= 2x SOA margin hot")
uv_hi, uv_lo = 115 / 15 * 1.24 + 3e-6 * 100e3, 115 / 15 * 1.14 + 3e-6 * 100e3
row("Switch UVLO (EN/UVLO 100k/15k + 0-5 uA EN sink)", f"on {uv_hi:.1f} V / off {uv_lo:.1f} V typ", f"off {1.027*115/15*0.98:.2f}-{(1.235*115/15+5e-6*100e3)*1.016:.2f} V, on <= {(1.32*115/15+5e-6*100e3)*1.016:.2f} V (1 % resistors, EN sink 0-5 uA); C18 filters the weapon ripple (1.3 ms): below a tired 4S pack under load (~11.5 V average) as long as firmware folds back current at ~12 V; limits an unloaded quick re-close step to ~9 V (loaded bounce: DESIGN 7.2)")
rtot = 1 / (1 / 6.8e3 + 1 / 66e3)
row("Bus decay after the switch opens (R15 6.8k ∥ ~66k of DC dividers, ~374 uF)", f"tau ~{rtot*374e-6:.1f} s; the switch UVLO (~9.0 V typ, 7.7 V min) opens about when the buck stops (~9.2 V), i.e. within ~0.1 s (typical) to ~0.4 s (minimum threshold)",
    "a re-close before that finds the FETs on (see spice/hotplug.out: under 4 V/us in every case); later re-closes are soft.  The weapon phase dividers have no DC path from VBAT while the bridge is Hi-Z")
row("INA239 limits", "SOVL 0x76C0 = 38 A, BOVL 0x17C0 = 19.0 V", "ADCRANGE = 1 (1.25 uV/LSB -> 1.25 mA/LSB at 1 mOhm); BOVL 3.125 mV/LSB")
row("Sensor supply short (per connector)", "TPS22945: 100-200 mA for 5-20 ms, then off, 80 ms auto-retry", "worst case 0.66 W for 20 ms in U11/U12; the +3V3 LDO (600 mA) stays in regulation; 4.7 uF at VIN covers the switch's response time")
row("Motor NTC line shorted to a phase", f"(16.8 - 4.0) / 2.2k = {(16.8-4.0)/2.2:.1f} mA into the BAV99", f"clamped to ~+3V3 + 0.7 V; R113/R117 0603 dissipate {(16.8-4.0)**2/2200*1000:.0f} mW (100 mW rating)")
row("Motor NTC series 2.2k", "adds a fixed 2.2 kOhm to the NTC reading", "subtract in firmware (R_ntc = R_meas - 2.2k)")
# buck UVLO: node equation with SHDN pull-up current 1 uA below / 4.2 uA above threshold (SNVSA24 7.5)
r1, r2 = 390e3, 51e3
for vth in (1.05, 1.25, 1.38):
    rise = r1 * (vth / r2 - 1e-6) + vth
    fall = r1 * (vth / r2 - 4.2e-6) + vth
    row(f"Buck UVLO at SHDN threshold {vth} V", f"on {rise:.1f} V / off {fall:.1f} V", "390 k / 51 k; typ = 1.25 V" if vth == 1.25 else "datasheet min/max threshold")
row("UVLO vs weapon sag", "off <= 10.3 V worst case vs 13.7 V minimum bus during a 25 A spin-up", "margin for a tired pack; firmware warns long before (3.5 V/cell)")
row("Drain with the buck off (switch closed, pack flat)", "~1.3-1.5 mA (R15 bleeder + DC dividers) until the switch UVLO opens at ~9 V", "then ~0.1-0.2 mA (R13/R14 + U13 in UVLO): switch the robot off after use")
row("Drain switched on and idle", "~95-113 mA (~1.6-1.9 W: logic through the buck, awake drivers, dividers)", "flattens a 450-650 mAh pack in 2-3 h: the board is not pack protection")

# ---------------------------------------------------------------- drive motor
table("10. Drive motor: Repeat Mini Mk4.1 (1106, 3500 KV, 28.5:1), 43.2 mm wheels")
KV, RATIO, WHEEL_R, PP = 3500, 28.5, 0.0216, 6            # 1106 = 9N12P typical: 6 pole pairs (confirm on the motor)
MASS = 0.454
VFRAC = 0.79          # usable line voltage with the ~81-86 % duty caps (flat-bottom SVPWM), review round 6
for v, tag in ((VBAT_MAX, "full 4S"), (14.0, "4S under load")):
    rpm = KV * v * VFRAC
    speed = rpm / RATIO / 60 * 2 * pi * WHEEL_R
    row(f"Top speed ({tag}, {v:.1f} V, duty-capped)", f"{rpm/1000:.1f} k rpm motor, {rpm/RATIO:.0f} rpm wheel, {speed:.1f} m/s ({speed*2.237:.1f} mph)",
        f"electrical frequency {rpm/60*PP/1000:.1f} kHz ({PP} pole pairs); field weakening only in sensorless mode (MT6701 rated 55 k rpm)")
kt = 60 / (2 * pi * KV)
row("Torque constant", f"{kt*1000:.2f} mN m/A", "Kt = 60 / (2 pi KV)")
for i in (0.5, 1.0, 1.5, 2.0, 4.0):
    f = kt * i * RATIO * 0.8 / WHEEL_R
    row(f"Tractive force per wheel at {i:.1f} A (80 % gearbox)", f"{f:.1f} N", "")
for mu in (1.0, 1.3):
    fmax = MASS * 9.81 / 2 * mu
    row(f"Traction limit per drive wheel (mu {mu}, half the weight)", f"{fmax:.1f} N = {fmax / (kt * RATIO * 0.8 / WHEEL_R):.2f} A",
        "the useful FOC current limit per motor; more only spins the tyre")
row("Stall current if uncontrolled", "~50-80 A at 16.8 V (1106 at 3500 KV, ~0.2-0.3 ohm line-line, not published)",
    "FOC current limit + DRV8316C OCP 16 A: never run open-loop at speed; measure R on the real motor")
row("FOC update rate", f"48 kHz = {48e3/(KV*14.0*VFRAC/60*PP):.1f} updates per electrical cycle at 14 V ({48e3/(KV*16.8*VFRAC/60*PP):.1f} at 16.8 V top speed)",
    "24 kHz would give only ~5; with the duty cap the motor tops out at ~47 k rpm, inside the MT6701's ~55 k rpm rating")

# ---------------------------------------------------------------- board heat budget
table("11. Board heat budget")
items = [("Weapon bridge, 20 A burst (per switching FET 0.84 + 1.1 W, 2 FETs active + shunts)", 2 * 1.94 + 3 * 0.8 * 2 / 3, 0.15),
         ("Drive channels at 1.5 A each (typ, 48 kHz)", 2 * sum(drv_loss(1.5, 0.140, 200e6, 0.5e-6)), 0.6),
         ("R302/R402 VM filters at 1.5 A rms each (incl. PWM ripple)", 2 * 0.24, 0.6),
         ("Switch FETs Q7+Q8 + RS4 at 22 A burst", 2 * 0.0014 * 1.5 * 22**2 + 0.001 * 22**2, 0.15),
         ("DRV8323 quiescent + weapon gate drive (VCP)", 16.8 * 0.012 + 3 * 60e-9 * 24e3 * 27, 1.0),
         ("Buck (85 %) + LDO + logic", 2.25 / 0.85 * 0.15 + 0.2 + 0.4, 1.0)]
avg = 0
for n, pk, duty in items:
    row(n, f"{pk:.1f} W peak", f"~{duty*100:.0f} % duty in a match -> {pk*duty:.2f} W average")
    avg += pk * duty
row("Total average over a 3-minute match", f"~{avg:.1f} W", "spread over the board; copper pours + chassis airflow; weapon/switch bursts are thermal-mass limited, not steady state")

text = "# Motor board design calculations (generated by calcs.py - do not edit)\n" + "\n".join(out) + "\n"
Path(__file__).with_name("calcs.md").write_text(text)
print(text)
