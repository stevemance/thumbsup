# Round 8 follow-up: C18 value vs loaded contact bounce (2026-09-24)

Question (round8_a R8A-01): C18 (EN/UVLO filter) delays the switch UVLO, so a contact bounce under a
20 A weapon load re-closes with the FETs still on.  Is there a C18 value that filters the 24 kHz
weapon ripple (the reason for C18, R7A-01) *and* keeps a loaded bounce soft?

Method: `spice/sim_hotplug.py` `run()` with `iload=20.0`, stiff pack (4 × 5 mΩ, 50 nH lead), typical
UVLO thresholds, re-close after the bounce; peak VM dV/dt.

C1 ESR 300 mΩ (its −40 °C limit), C18 swept:

| C18 | 0.05 ms | 0.1 ms | 0.2 ms | 0.3 ms | 0.5 ms | 0.8 ms | 1.2 ms |
|---|---|---|---|---|---|---|---|
| none | 0.08 | 0.08 | 0.08 | 0.09 | 0.09 | 0.09 | 0.09 |
| 10 nF | 3.13 | 4.17 | 0.08 | 0.09 | 0.09 | 0.09 | 0.09 |
| 22 nF | 3.13 | 4.17 | 4.33 | 4.32 | 0.09 | 0.09 | 0.09 |
| 100 nF | 3.13 | 4.17 | 4.33 | 4.32 | 4.30 | 4.31 | 4.33 |

(V/µs.)  Any C18 large enough to matter leaves a hard re-close window; only "none" avoids it, and
that brings back the ripple trip (0.47–0.64 V of 24 kHz ripple at the EN pin, R7A-01).

C18 = 100 nF, bounce vs C1 ESR (typical and minimum UVLO give identical results):

| C1 ESR | 0.1 ms | 0.3 ms | 0.8 ms |
|---|---|---|---|
| 20 mΩ (new, 20 °C) | 1.46 | 2.45 | 2.51 |
| 40 mΩ (aged) | 1.87 | 3.01 | 3.05 |
| 60 mΩ | 2.14 | 3.37 | 3.37 |
| 100 mΩ | 2.58 | 3.75 | 3.75 |
| 150 mΩ | 3.03 | 4.02 | 4.02 |

Decision: keep C18 = 100 nF (it also cuts Q7's dissipation in a tired-pack UVLO hiccup ~10×) and
define the operating envelope as ambient ≥ 0 °C (DESIGN §1).  Round 9 (R9A-01): the Panasonic ZK
sheet only gives 20 mΩ new / 40 mΩ aged at 20 °C and 300 mΩ aged at −40 °C, so the defensible aged
0 °C bound is ~100 mΩ (interpolated), not 60 mΩ: worst **3.76 V/µs** inside the envelope (~6 % margin; the table's 3.75 is 3.755 rounded).  Rev K (round 10) added the R302/R402 VM filters: the same cases are now ≤ 2.25 V/µs (2.65 at −40 °C), see DESIGN §7.2.  The
loaded bounce is a documented residual (DESIGN §7.2) and is in `spice/hotplug.out`.
