# Adversarial check: "the 10 µF 1206 VM caps are half the capacitance the design assumes"

Date 2026-09-29.  No repo files were edited.  Scratch work is in `/tmp/adv_mlcc/`:
* `sim_var.py`: a copy of `spice/sim_hotplug.py` with a **voltage-dependent** MLCC model option.
* `runall.sh` and `summ.py`: the runner and the summary script.
* `v_*.out`: the run outputs.
* The vendor PDFs and the cropped curves `mur_dcbias.png` and `g71_dcbias.png`.

## Verdicts

| # | Claim | Verdict |
|---|---|---|
| 1 | CL31A106KBHNNNE keeps ~22 % at 16.8 V, and the design assumes ~4 µF each | **CONFIRMED** by a second vendor.  The design text is wrong at 16.8 V |
| 2 | Hot-plug worst case rises 2.26 → 3.39 V/µs (4.15 at −40 °C) | **Numbers reproduced, conclusion REFUTED.**  The rise is an artefact of modelling the caps as linear at their 16.8 V value.  The peaks happen at VM ≈ 6–9 V, where these parts have 2.5–3× more capacitance |
| 3 | 2 × CL32A106KBJNNNE 1210 per drive (~7 µF each) is the fix | **The 1210 bias figure is plausible** (Murata's equivalent 1210 part gives −24 %).  But it is not needed to meet 4 V/µs.  Its real value is at 16.8 V: ~15 µF against ~9 µF today, in less area |
| 4 | DRV8316 VM limit is 4 V/µs | **CONFIRMED** |

## 1. DC bias of the current part

**Part check.** `design/motor_board.py:60` maps `"10u_50V_1206": "C13585"`.  C13585 is CL31A106KBHNNNE (LCSC), and the BOM shows 11 of them:
* C25, C26, C31 (VBAT);
* C302, C308, C309, C310 (U3 VM filter);
* C402, C408, C409, C410 (U4 VM filter).

**Where the design states its assumption:**
* `design/motor_board.py:291`: "1206 50 V X5R keeps ~4 uF at 16.8 V each".  Line 292 says "~16 uF effective".
* DESIGN.md:209 and :36: "~16 µF effective at 16.8 V".
* `design/calcs.md:87`: "4 x 10 uF ~16 uF".
* `spice/sim_hotplug.py`: `cvm="16u"` per drive branch, and `cm 12u` on VBAT (3 × 4 µF).

**Samsung.** I parsed the proposer's saved Samsung page (`sam31.html`) myself.  Samsung's live site was returning HTTP 500 during this review.  The DCBias curve for CL31A106KBHNNN gives:

| DC bias | 5 V | 10 V | 16 V | 16.8 V | 25 V |
|---|---|---|---|---|---|
| Change | −27 % | −59 % | −77 % | **−78 %** | −87 % |

**Independent second source: Murata GRM31CR61H106KA12** (1206, X5R, 50 V, 10 µF, 1.6 mm).  Datasheet page 2, "C-DC bias, 25 °C, AC 1 Vrms", from https://www.farnell.com/datasheets/2048767.pdf:

| DC bias | 5 V | 10 V | 15 V | 16.8 V | 20 V |
|---|---|---|---|---|---|
| Change | ≈ −25 % | ≈ −55 % | ≈ −73 % | **≈ −76 %** | −80 % |

So the effective value at 16.8 V is **~2.2–2.4 µF per part, ~9 µF per drive and ~7 µF on VBAT**.  The design's "~4 µF / ~16 µF" figure came from r5's generic curve, which was marked UNVERIFIED.  It overstates the capacitance by about 1.8×.

**Temperature** (not modelled by either side): Murata's TCC curve at 0 V bias gives about −2 % at 0 °C and about −8 % at −40 °C.  My derated run below uses 0.81 × C0, which covers −10 % tolerance plus about −10 % for cold and aging.

## 2. Hot-plug sims

**Baseline.** I ran `spice/sim_hotplug.py` from a fresh copy through KiCad's libngspice.  The output is **identical** to `spice/hotplug.out`.

**Proposer's linear variants.** I reproduced them exactly:
* CM 6.6 µF, CVM 8.8 µF → 3.33 / 3.39 V/µs (0 °C bounds), **4.15** at −40 °C, 3.23 min-UVLO re-close.
* 2 × 1210 linear at 14 µF → 2.51 / 3.03 / 2.40.

**Modelling flaw.** Both the repo sim and the proposer's patch use *linear* capacitors.  I added a report of VM at the instant of peak dV/dt.  **Every worst-case peak happens at VM ≈ 6–9 V**, while the bus recovers from a bounce or re-close that starts at 4.4–8.9 V.  It never happens near 16.8 V.
* At 7 V a CL31A keeps about 60–65 %, i.e. about 6 µF, not 2.2 µF.
* So "linear at the 16.8 V value" is a large overestimate of the risk.
* The design's original "linear 16 µF" happened to sit close to the truth for these events.

**Nonlinear model.** I modelled each bank as a charge source Q(V) = C·V0·atan(V/V0), which gives a differential capacitance C/(1+(V/V0)²).  It is built from an E-source, a 0 V sense source, a 1 µF reference cap and an F-source.
* **Validation:** with V0 → ∞ it reproduces the linear 4 µF case to 4 digits (2.2582 vs 2.2582).
* **1206 fit, V0 = 8.92 V:** 5 V 0.76, 10 V 0.44, 16.8 V 0.22, 25 V 0.11.  This tracks Samsung and Murata within about 0.03.
* **1210 fit, V0 = 25.66 V:** −30 % at 16.8 V, Samsung's CL32A figure.  A Murata variant with V0 = 29.9 V gives −24 %.
* **Solver step:** capping the step at 1 µs or 0.5 µs changes the results by ≤ 0.5 %.  At 0.3 µs the nonlinear model does not converge.

Worst-case peak dV/dt at the DRV8316 VM pins, in V/µs:

| Variant (VBAT caps nonlinear 1206 in all nonlinear rows) | 0.3 ms bounce, 0 °C | 0.8 ms bounce, 0 °C | −40 °C bounce | min-UVLO re-close | VM at peak |
|---|---|---|---|---|---|
| As committed (linear 16 µF) | 2.21 | 2.26 | 2.66 | 2.09 | 6.6–8.0 V |
| Proposer: linear at 16.8 V value (8.8 µF) | 3.33 | 3.39 | **4.15** | 3.23 | 6.7–7.6 V |
| **4 × 1206, nonlinear (real parts, as designed)** | **1.76** | **1.76** | **2.27** | **2.20** | 7.2–8.3 V |
| 4 × 1206, nonlinear, C0 × 0.81 (tolerance, cold, aging) | 2.12 | 2.12 | 2.79 | 2.67 | 7.6–9.0 V |
| 4 × 1206, nonlinear, steeper fit (V0 = 8.0 V) | 1.92 | 1.92 | 2.53 | 2.52 | |
| 2 × 1210, nonlinear (Samsung −30 %) | 2.14 | 2.16 | 2.67 | 2.16 | |
| 2 × 1210, nonlinear (Murata −24 %) | 2.11 | 2.14 | 2.62 | 2.09 | |
| 2 × 1210, nonlinear, C0 × 0.8 | 2.51 | 2.57 | 3.19 | 2.57 | |
| 3 × 1210, nonlinear | 1.57 | 1.59 | 1.93 | 1.58 | |
| 4 × 1210, nonlinear | 1.24 | 1.27 | 1.51 | 1.23 | |

**Conclusion.** With a physically correct C(V) model, the design as drawn stays **≤ 2.3 V/µs, and ≤ 2.8 V/µs with 19 % derating, even at −40 °C**.  "3.39 / 4.15 V/µs" is not a real exceedance.
* round11_a N-07's "8 µF → 3.47 V/µs" is the same linear artefact.
* The committed `hotplug.out` numbers are close to the nonlinear truth by coincidence.  They are right for the wrong reason.

## 3. The 1210 fix and alternatives

**1210 DC bias, independent check.** Murata GRM32ER71H106KA12 (1210, X7R, 50 V, 10 µF, T = 2.5 mm) gives:

| DC bias | 10 V | 15 V | 16.8 V | 20 V | 30 V |
|---|---|---|---|---|---|
| Change | ≈ −9 % | ≈ −20 % | **≈ −24 %** | ≈ −31 % | ≈ −52 % |

Source: its datasheet page 2, https://datasheet.octopart.com/GRM32ER71H106KA12L-Murata-datasheet-62317418.pdf.  That is **~7.6 µF at 16.8 V**, which is consistent with Samsung's −30 % (~7 µF) for CL32A106KBJNNNE.  I could not re-fetch Samsung's CL32A page (their server returned 500), so the Samsung 1210 figure is corroborated only by the Murata part, not re-read.

**Alternatives with a better-biased part in 1206.** None is realistic.
* 10 µF / 50 V in a 1.6 mm-tall 1206 needs thin dielectric layers.
* X7R 1206 10 µF / 50 V parts (TDK CGA5L1X7R1H106K C531431, CCTC, HRE) use the same construction.  Expect a similar ~−75 % at 16.8 V (not verified: the TDK tool is blocked).
* I found no 22 µF / 50 V 1210 MLCC stocked at JLC.

**Capacitance per area.** Courtyard areas are the proposer's: 1206 = 10.6 mm², 1210 = 14.7 mm².

| Option | Area / drive | C at 16.8 V | C at ~7 V (hot-plug peak) | Worst hot-plug (−40 °C) |
|---|---|---|---|---|
| 4 × 1206 (today) | 42.4 mm² | ~9 µF (0.22 µF/mm²) | ~25 µF | 2.27 |
| 2 × 1210 | 29.4 mm² | ~14–15 µF (0.50 µF/mm²) | ~19 µF | 2.62–2.67 |
| 3 × 1210 | 44.1 mm² | ~21–23 µF | ~28 µF | 1.93 |
| 4 × 1210 | 58.8 mm² | ~28–30 µF | ~37 µF | 1.51 |

For the hot-plug the 1206 and the 1210 are about equal per mm², because the event happens at low bias.  At the 16.8 V operating point the 1210 gives about 2.3× more capacitance per mm².

**What sees the 16.8 V value (not re-simulated):**
* **The weapon fault-clear kick.** Round 9/10 reviewer sims gave 9–11 → ~1–2 V/µs with "16 µF".  They are not in `spice/`, per R10B-N06.  With ~9 µF the RC time constant drops from 1.6 to about 0.9 µs, so the kick at VM could be up to about 1.5–2× larger, i.e. ~2–3.5 V/µs.  **This is the actual open risk.**  The ~16 µF assumption behind that number is wrong, and it should be re-simulated.
* **The R302/R402 ripple share and DRV8316 VM ripple.** The corner moves from ~99 kHz to ~180 kHz, so more drive ripple goes through R302.
* **`sim_weapon_bridge.py`.** It idealises the bridge MLCCs as 20 µF.  The real value at 16.8 V is about 7 µF for C25/C26/C31.

## 4. The DRV8316C VM ramp limit

TI SLVSH07 (December 2022), §7.1 Absolute Maximum Ratings, from https://www.ti.com/lit/ds/symlink/drv8316c.pdf:
* "Power supply voltage ramp (VM) … MAX 4 V/µs".
* VM pin voltage: −0.3 V to 40 V.

**Confirmed.**  The same datasheet recommends CVM2 "≥ 10 µF" rated at "least twice the normal operating voltage".

## Recommendation

**Configuration: 2 × 10 µF 50 V 1210 per drive in place of 4 × 1206.**
* Part: preferably Murata **GRM32ER71H106KA12L (C77102**, X7R, 68 k JLC stock, Extended).  Its DC-bias curve is the one verified here.  The fallback is Samsung CL32A106KBJNNNE (C380537).
* It gives ~15 µF at 16.8 V, which **makes the documented "~16 µF per drive" assumption true**.  That assumption underlies the fault-clear-kick and R302 numbers.
* It keeps the hot-plug at 2.1–2.7 V/µs (3.2 derated at −40 °C), about the same as today.
* It saves 13 mm² and 2 placements per drive.
* **If layout can spare the area: 3 × 1210 per drive** (≈ today's footprint) is the better-margin choice: ~22 µF at 16.8 V, ≤ 1.93 V/µs hot-plug.
* Apply the §6.10 flex-crack placement rules to the 1210s.

**Other actions:**
* Correct the "~4 µF each" text in `motor_board.py:291`, DESIGN §3.3 and calcs §7.
* Optionally make `sim_hotplug.py` use a C(V) model.
* Add and re-run the weapon fault-clear-kick sim with the real 16.8 V capacitance.
* Leave C25/C26/C31 as they are for the hot-plug (C1 dominates), but note the ~7 µF reality for `sim_weapon_bridge.py`.
