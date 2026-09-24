# Review round 3 — A: power entry (rev C: Q7/Q8, gate network, D1, C1, RS4/U7, R4/R5/C10, LED)

Reviewer scope: the rev C power entry (R2A-02 fix) and a re-check of the parts around it.
Evidence: `design/motor_board.py` (regenerated in a temp copy: "checks: OK", outputs identical to
the committed `design/`), datasheets in `datasheets/`, the CJ B5819W datasheet (not in the package,
fetched for this review), and ngspice runs based on `spice/sim_hotplug.py`, all run from copies in
`/tmp/r3a/sp/` (the scripts are summarised in the appendix).  No design file was edited.

Netlist lines used throughout (motor_board.py 97–127, 128–152):
`Q7 D=BAT_NEG S=RPP_S G=RPP_G`, `Q8 D=GND S=RPP_S G=RPP_G`, `R1 VBAT–RPP_G 100k`,
`D4 K=RPP_G A=RPP_S`, `C12 RPP_G–RPP_S 220n`, `C13 RPP_G–GND 10n`, `D6 K=VBAT A=RPP_G (B5819W)`,
`D5 K=CELL0 A=GND (B5819W)`, `R6 BAL0–CELL0 100R 0402`, `U8 VSS=GND, VC0=CELL0`.

---

## R3A-01 — BLOCKER: every normal power-on lifts board GND to pack+ while the balance lead is plugged, driving U8's VC1–VC6 pins up to 12 V below VSS

**Mechanism.** The switch is in the + wire and the inrush limiter is in the ground return.  When the
switch closes, C1 (uncharged) carries VBAT's step onto GND, and the only way from GND back to
pack− is Q8's channel, which is still off (Q8's body diode points RPP_S→GND).  For the whole
turn-on delay plus the ramp, **board GND sits at ~pack+ relative to pack−**.  That is how the
limiter works, and it is harmless as long as nothing else on the board is tied to pack−.  The
balance lead is tied to pack−: J4 B0…B4 sit at 0 / 4.2 / 8.4 / 12.6 / 16.8 V above pack−, and
U8's VSS is board GND, so relative to VSS the taps are at −16.8 / −12.6 / −8.4 / −4.2 / 0 V.
Before rev C, Q7's body diode tied GND to pack− at the first instant, so this could not happen.
The problem came in with the R2A-02 fix.

This is the normal power-on sequence.  DESIGN §3.1 says "main lead first, balance lead second";
the balance lead stays plugged for cell logging (§4a); then the chassis switch is closed.

**Datasheet limits** (BQ76907 §6.1 Absolute Maximum Ratings): VC0 ≥ VSS−0.3 V; VCn ≥ max(VSS−0.3 V,
VC(n−1)−0.3 V) for VC1…VC7; BAT ≥ VSS−0.3 V.

**Simulation.** I added the balance lead to `sim_hotplug.py`: 4 cells, 50 mΩ + 200 nH per tap wire,
R6–R10 100 Ω, C4–C8 220 nF, D5 (B5819W fit), R11 + C9 (2 µF effective) and a 100 k U8 load.  The
switch is truly open before closure (roff 1e12, see R3A-04).  Nominal pack.

| Case | VC0−VSS min | VC1−VSS min | VC2 | VC3 | VC4 (=VC7 net CELL4) | R6 peak / energy | D5/R6 current > 20 mA for |
|---|---|---|---|---|---|---|---|
| U8 pins unclamped (the voltage the pins are pushed to) | −0.51 V | **−12.35 V** | **−8.89 V** | **−5.12 V** | **−1.74 V** | 6.4 W / 5.8 mJ | 3.0 ms |
| U8 pins modelled with ESD diodes to VSS and between adjacent VC pins (structure UNVERIFIED) | −0.51 V | −1.19 V | −1.05 V | −0.84 V | +0.19 V | 6.4 W / 5.4 mJ | 3.0 ms |

Each tap carries 240–500 mA peak.  With clamps, VC1 to VC3 are pulled below VSS through 100 Ω for
~3 ms at roughly (12.6−0.7)/100 ≈ 120 mA, 80 mA and 35 mA into U8's ESD structures, on every
power-on.  R6 (0402, 1/16 W) takes a 6.4 W peak and 5–6 mJ in 3 ms, about 30× its rating averaged
over the pulse.  VC0 itself reaches −0.51 V (limit −0.3 V) during the first µs, before D5 takes
over.  Likely results: U8 latch-up or damage, drift in R6–R9, and the cell readings becoming wrong
over time.

**Fix options** (for the designer; none is free):
1. **Move the inrush limiter to the high side**, so GND is tied to pack− from the first instant.
   Q7 stays low-side as the reverse-polarity FET, and a high-side P-FET or a hot-swap controller
   limits the inrush.  This fixes the root cause.
2. **Keep the low-side limiter and harden the balance inputs.** R6–R10 → 1 kΩ (TI's maximum),
   C4–C8 → 100 nF (RC 100 µs ≤ 200 µs, ≥ 0.1 µF), and low-leakage Schottky clamps GND→CELL1…CELL3
   as well as D5.  Simulated: VC0…VC3 ≥ −0.30 V, cell differentials ≥ −0.02 V, 27 mA per tap, R6
   0.74 W peak / 0.5 mJ.  This sits right at the −0.3 V limit, and clamp leakage flowing through
   1 kΩ becomes a cell-reading error (hot B5819W leakage would be ~0.1–0.8 V, so a lower-leakage
   part is required).  Marginal.
3. **Operating rule:** close the main switch with the balance lead unplugged, then plug it in (the
   hot plug D5 was sized for).  This is probably impractical in a closed chassis.

Whichever is chosen, `sim_hotplug.py` must model the balance lead.

---

## R3A-02 — MAJOR: the "re-close is soft after the bus discharges" claim is a load-model artifact; the real unprotected window is ~10 s, not ~10 ms

DESIGN §5 and §7.2 say: re-close after 2 ms → 1.0 V/µs, after ~10 ms → 3.5–4.2 V/µs, after
50 ms → 0.1 V/µs; "any re-close after a full discharge soft"; "A screw switch cannot do this".
All of these come from the sim's fixed **30 Ω** load, which drains C1 with τ ≈ 11 ms down to 0 V.

What the board actually does after the switch opens:
* The buck and compute board are a roughly constant-power load until the buck stops.  U2 nSHDN is
  filtered by R4‖R5·C10 = 4.5 ms (EN falling equivalent 9.2 V; LMR16006 VIN UVLO falling ~3 V,
  LMR16006 EC table).  Integrating 1–3 W from 16.8 V into 360 µF gives a buck stop at 4.7–7.8 V
  after 16–40 ms.
* After that, the VBAT load is tiny: R63+R64 78 k, R4+R5 441 k, DRV8323 sleep 12–50 µA (SLVSDJ3D
  EC IVMQ), DRV8316 sleep 2.5–5 µA each (SLVSH07 IVMQ; nSLEEP = +3V3 is now low), LMR16006 1–3 µA.
  Equivalent ≈ 30–35 kΩ → **τ ≈ 11–12 s**, and 8–13 s to fall to 2.5 V.
* D6 only pulls the gate down to VBAT+VF, so **Q7/Q8 stay fully on (Vgs ≈ 5 V) for ~10 s** with
  the bus at ~5 V.

Sim (copy of `sim_hotplug.py` with the 30 Ω replaced by a 3 W constant-power load that drops out
below 6 V, plus 35 kΩ; stiff pack 20 mΩ, 50 nH lead; re-close after 100 ms):

| C1 ESR | bus / Vgs before re-close | max dV/dt at VM | surge |
|---|---|---|---|
| 20 mΩ | 5.26 V / 5.27 V | 3.20 V/µs | 199 A |
| 40 mΩ | 5.26 V / 5.27 V | 3.87 V/µs | 176 A |
| 100 mΩ (cold) | 5.26 V / 5.27 V | **4.70 V/µs** (> 4 V/µs DRV8316 abs max, SLVSH07 §6.1 "Power supply voltage ramp (VM) 4 V/µs") | 163 A |

The state is the same at any re-close up to ~10 s.  So switching off and back on within a few
seconds, which happens in the pits, at the arena door, or when an inspector asks for a power
cycle, is an unlimited hot plug from ~5 V.  The power LED gives no warning: it goes out when the
buck stops (~5–8 V), long before the gate turns off.  §7.5 has the same effect with a coasting
drum holding the bus up.

**Fix:** discharge the gate, or the bus, when the logic rail is gone rather than when VBAT
collapses.  For example, a small N-FET from RPP_G to RPP_S driven while +3V3 is absent, or a
~100 Ω bus bleeder switched on by the absence of +5V.  Re-simulate with the constant-power +
~35 kΩ load.  At minimum, correct §5/§7.2 and add an operating rule ("after opening the switch,
wait ≥ 20 s before re-closing"); the §7.2 claim that "a screw switch cannot do this" is wrong.

---

## R3A-03 — MINOR: D6 (B5819W) reverse leakage is in parallel with R1 and multiplies the inrush current when hot

D6 is reverse biased by VBAT−V(RPP_G), which is ~14 V during the ramp.  That leakage adds to R1's
~146 µA gate current, and the ramp rate is I_gate / C13.  CJ B5819W datasheet (the LCSC C8598
maker): IR max **1 mA at 40 V, 25 °C**; typical-curve IR at 14 V ≈ 10 µA (25 °C), ~90 µA (75 °C),
~0.8 mA (100 °C).

| D6 leakage | delay | ramp (avg) | inrush | Q8 peak power / energy |
|---|---|---|---|---|
| none (as modelled) | 1.26 ms | 0.012 V/µs | 5.1 A | 57 W / 50 mJ |
| 90 µA (75 °C typ) | 0.83 ms | 0.019 V/µs | 7.9 A | 74 W / 48 mJ |
| 0.8 mA (100 °C typ) | 0.26 ms | 0.061 V/µs | 27 A | 204 W / 40 mJ |
| 1 mA (datasheet max, 25 °C) | 0.22 ms | 0.070 V/µs | 32 A | 231 W / 39 mJ |

The ramp stays far below 4 V/µs, so the limiter still does its main job.  But "5 A inrush in every
case" (§1, §4, §5) is not true for a hot board, such as a pack swap right after a match.  Q8's
margin also shrinks.  HYG Fig. 3 SOA is at Tc = 25 °C and Fig. 4 gives Zθjc ≈ 0.25 °C/W at
0.2 ms.  A 230 W triangle over ~0.2 ms is ~35 °C of rise, and the SOA derated to Tc = 100 °C
leaves roughly 1.3–2× margin.  Linear-mode (Spirito) behaviour at Vgs ≈ 2–2.5 V is not covered by
the datasheet curve: UNVERIFIED.  **Fix (cheap):** D6 → a low-leakage switching diode (1N4148WS /
BAS16-class, IR ≲ 1 µA hot at 15 V).  D6 only has to carry the C12 discharge, so its VF does not
matter.

---

## R3A-04 — MINOR: `sim_hotplug.py` fidelity problems, and the numbers they put into the docs

1. **"Open" switch = 10 MΩ.** Before closure it trickle-charges the gate to Vgs = 1.24 V
   (timeline dump: t = 0.99 ms, Vgs 1.24 V, bneg −1.24 V), so the modelled turn-on delay is
   0.37 ms.  With roff = 1e12 the delay is 1.07–1.35 ms over Vth = 1.2–2.5 V (HYG EC table).
2. **The dV/dt metric catches the closure instant**, not the ramp.  The reported 0.06–0.08 V/µs
   maxima occur 1 µs after closure with VM = 0.00 V (a Coss/lead ringing spike).  The real ramp is
   **0.012 V/µs** (10–90 % in 1.1 ms), which fits I_R1 / C13 = 146 µA / 10 nF and 5.1 A into
   ~360 µF.  The docs quote 0.04 (netlist comment, line 93; C13 desc "~0.04 V/us, 5-8 A"), ~0.05
   (DESIGN §3.1 "sets ~0.05 V/µs") and ≤ 0.08 V/µs (§1, §4, §5), and "5 A for ~3 ms" (§4).
   Actual: ~1.2 ms delay then 5 A for ~1.1 ms.  All of these are harmless, but they disagree.
3. **30 Ω load**: see R3A-02 (the bounce conclusions depend on it).
4. **No balance lead**: see R3A-01.
5. **No D6 leakage**: see R3A-03.
6. Adequate: the VDMOS fit (vto 1.9 V = datasheet typ; kp 180 gives ~2.1 V plateau at 5 A; it
   overstates Fig. 5 gm by ~1.4× at 3.5 V, which changes the ramp by ~1 %), the zener (sharp 12 V
   at 1 mA; the MMSZ5242B at 48 µA is below IZK and sits somewhat lower, which only affects the
   final Vgs), and the TVS fit (23.3 V + 0.49 Ω → 32.4 V at 18.6 A = SMBJ20A table).

Fix: roff = 1e12, measure the ramp after VM > 0.5 V, use a constant-power + ~35 kΩ load, add the
balance-lead and D6-leakage cases, and update the numbers in DESIGN §1/§3.1/§4/§5 and the netlist
comments.

---

## R3A-05 — NOTE: under pack current, D5 conducts and cell 1 reads low

Board GND sits above pack− by I × (Q7 + Q8 + pad copper + negative lead + XT30 + the pack's
internal negative wire).  Using 2 × 2.6 mΩ (1.7 mΩ max × ~1.5 hot, HYG EC table / Fig. 7)
+ ~4 mΩ wiring ≈ 9 mΩ, that is ≈ 0.2 V at 22 A and 0.24 V at the 27 A spin-up peak.  B0 carries
no current, so VC0 is pulled toward −0.24 V and D5 takes over.  With a B5819W fit
(is 3 µA, n 1.1), D5 conducts ~0.7 mA at VF ≈ 0.17 V: **VC0 ≈ −0.17 V (inside −0.3 V)**.  That
0.7 mA flows through R6, so **cell 1 reads ~50–70 mV low** during high current (low-current
Schottky fit is UNVERIFIED).  This matters for "logging cell sag under load" and for any BQ76907
cell-UV threshold on ALERT.  Fix: firmware/compute-board note (ignore or correct cell 1 while
|I| is high; the INA239 current is known), or a larger R6 (see R3A-01 option 2).

## R3A-06 — NOTE: a second ground path bypasses Q7/Q8

If the compute board is USB-connected to an earthed PC while the pack or bench supply negative is
also earthed (for example a charger-connected pack or a non-floating bench supply), board GND is
tied to pack− through the USB ground.  The plug-in surge and part of the running current then
flow through the USB/compute-board ground, and a reversed supply is not blocked.  Add to the §9
bring-up notes: floating supply, or no USB, while powering from the battery pads.

## R3A-07 — NOTE: stale documentation around the power entry

* `datasheets/README.md`: D5 is listed as "BAT54WS_Diodes.pdf | VC0 clamp D5" but D5 (and D6) are
  B5819W, and no B5819W datasheet is in the package.  The HYG row says "Q1–Q6, reverse-polarity FET
  Q7" and should add Q8.
* `motor_board.py` U7 desc: "only SOVL enabled"; §8 says SOVL + BOVL.
* DESIGN §3.1 "On: 2 × 1.4 mΩ, ~2 W together at 22 A (hot)": with max RDS hot (2 × ~2.6 mΩ) it is
  ~2.5 W.  Still fine for 0.5 s bursts.

---

## VERIFIED OK

* **Plug-in dynamics / bounce** (true open switch, stiff pack, 50 nH): 5 × 50 µs chatter → 0.05 V/µs,
  5.2 A; 0.2 ms open mid-ramp → 0.30 V/µs, 7.9 A; 1 ms open right after the ramp → 0.50 V/µs,
  21.7 A; 0.3 ms open at Vgs ≈ 3.5 V → 0.17 V/µs.  All below 4 V/µs.
* **Pack at 12 V**: delay 2.1 ms, 0.0077 V/µs, 3.4 A, Q8 28 W / 25 mJ.  **300 nH lead**: 0.012 V/µs,
  5.2 A, no overshoot (VM peak 16.8 V).
* **Q8 SOA, nominal**: 57–61 W peak falling to 0 over 1.1 ms, 45–50 mJ.  HYG Fig. 4 Zθjc(1 ms)
  ≈ 0.5 °C/W gives ~20 °C of rise, against a Fig. 3 1 ms line of ≈ 300 W at 17 V (Tc 25 °C), about
  150 W derated to Tc 100 °C.  ~2.5× margin (hot-D6 case in R3A-03).
* **Gate at full charge**: (16.8−12)/100 k = 48 µA into the MMSZ5242B (VZ 11.4–12.6 V at IZT 20 mA,
  IZK 0.25 mA): Vgs ≈ 10.5–12.6 V < 20 V.  At the TVS clamp (32.4 V), 0.2 mA.  C12 25 V and C13 50 V
  have margin.  Vgs reaches 4.5 V ~6 ms and ~10 V ~20 ms after closure, before the MCU can load
  the bus.
* **Reversed pack**: Q7 body diode reverse, Vgs(Q7) ≤ 0 (R1 to VBAT = pack−, D4 clamps −0.7 V), D1
  sees nothing.  **With the balance lead plugged**: U8 is powered with the correct polarity and
  returns its ~150 µA through D5 (the lowest-VF path), so board GND ≈ pack− + 0.1 V and the U7/DRV
  pins sit ≈ −0.1 V with µA.  §7.1 is correct.
* **Regen** flows BAT_NEG → Q7 channel → Q8 body diode/channel.  A rising VBAT only increases the
  gate drive, so it cannot starve the gate.  GND then sits below pack−, which puts VC0 above VSS by
  ~0.2 V (limit VSS+6 V).
* **Brownout / low pack**: below ~11 V the zener is off and Vgs ≈ VBAT.  At 9 V, RDS is at the
  10 V spec; at 4.5 V, 2.0/2.4 mΩ (EC table).  VBAT dips below the gate (low pack under weapon load,
  PWM ripple) forward D6 and the gate peak-detects VBAT_min − VF.  That is harmless while
  VBAT_min > ~5 V, and below that the logic is already in UVLO.
* **C13 coupling**: gate sees C13/(C12+C13) = 4.3 % of any GND–RPP_S bounce.  Pack current is
  smoothed by C1 and the lead, so bounce across Q8 is ~I·RDS.  The closure kick is 0.7 V
  (sim) against Vth min 1.2 V; at hot Vth a brief partial turn-on would pull the same way as the
  intended turn-on.
* **Turn-on sequencing**: bus 0 → 16.8 V in ~1.1 ms at 0.012 V/µs.  DRV8316 UVLO (4.4 V rising,
  200 mV hysteresis, 5 µs deglitch) is crossed monotonically, and the Q8 Miller loop supplies the
  DRV8316 buck's start current without a dip.  U2's buck starts ~4 ms later through the 4.5 ms
  nSHDN filter, when Vgs ≈ 3.5 V (RDS tens of mΩ at ≤ 1 A, Fig. 5).  No latch path found.
  Injection into PA3 and into the compute board's VBAT_SNS pin through R63 68 k before VDD is up is
  ≤ 0.25 mA.
* **R4/R5/C10**: with the LMR16006 SHDN source currents (−1 µA below, −4.2 µA above threshold;
  1.05/1.25/1.38 V), on ≈ 10.4 V and off ≈ 9.25 V typ, off 7.4–10.3 V worst: matches calcs.  A
  depleted pack under a 22 A sag (~12.5 V) stays above the 10.3 V worst-case off.
* **INA239**: IN± and VBUS common mode −0.3…85 V (EC table).  The Q7/Q8 offset is outside its
  measurement loop (high-side shunt).  VBUS reads the board bus (RS4 + Q7/Q8 drops low, as
  documented).  R2/R3 10 Ω + C2 100 nF = 80 kHz; IB 0.1 nA → negligible offset.
* **RS4** 1 mΩ 3 W MnCu, ±50 ppm/°C (JIERR table, 1–4 mΩ large electrode): 0.48 W at 22 A.
* **D1** SMBJ20A: VRWM 20 V > 16.8 V and > BOVL 19 V; VBR 22.2–24.5 V; VC 32.4 V at 18.6 A < 35 V C1
  and < 40 V DRV8316.  After the FETs, so a reversed pack does not reach it.  Not involved in the
  plug-in (the limiter keeps VM ≤ 16.8 V).
* **C1** EEHZK1V331P: 330 µF, 20 mΩ, 2.8 A ripple (Panasonic table); 35 V > TVS clamp.
* **LED path**: (5 − 1.9…2.4 V)/1 k ≈ 2.6–3.1 mA, rating 25 mA (KT-0603R).
* **Netlist**: RPP_G/RPP_S/BAT_NEG/CELL0 connectivity and D4/D5/D6 polarity are as described in §3.1
  (nets.md regenerated in a temp copy, identical).

---

## Appendix — how the extra cases were run (copies in /tmp/r3a/sp, from spice/sim_hotplug.py)

* `probe.py`: timeline and metrics (10–90 % ramp, dV/dt after closure, Q8 P = V(GND−RPP_S)·I, energy).
* `cases.py`: roff 1e12; `vpack 12`; `lead_nh=300`; D6 leakage as
  `bleak vbat g i=IL*tanh((v(vbat)-v(g))/0.5)` with IL = 90 µA / 0.8 mA / 1 mA; `vth.py` vto 1.2/1.9/2.5.
* `balance.py`: vpack split into 4 × 4.2 V cells, taps `rw 50m + lw 200n + rin 100R`, C4–C8,
  `d5 0 cell0 (is=3e-6 n=1.1 rs=0.15)`, R11 + 2 µF, optional ESD diodes VSS→VCn and VC(n−1)→VCn.
* `reclose2.py`: `off_ms=100`, `rload 35k` + `bload i=3/max(v(vbat),1)*(1+tanh((v(vbat)-6)/0.2))/2`.
* `bounce.py`: arbitrary ctl PWL edge lists.

**Verdict: 1 BLOCKER, 1 MAJOR, 2 MINOR (plus 3 NOTE).**
