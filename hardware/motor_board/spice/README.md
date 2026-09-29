# Motor board SPICE checks

ngspice through KiCad's `libngspice` (`hardware/tools/spice/ngspice_shared.py`); no ngspice
binary needed.  Run with the hardware venv (numpy):

```
cd hardware/motor_board/spice
../../tools/.venv/bin/python sim_hotplug.py        # ~4 s (cases run in parallel)
../../tools/.venv/bin/python sim_arm.py            # ~5 s (cases run in parallel)
../../tools/.venv/bin/python sim_weapon_bridge.py  # ~1 min
../../tools/.venv/bin/python sim_fault_kick.py     # ~1 min
../../tools/.venv/bin/python sim_weapon_spinup.py  # seconds
```

| Script | Question | Model notes |
|---|---|---|
| `sim_arm.py` | Dynamic ARM charge pump (C15/D9/C16/R41 + U14): armed level, edges to arm, disarm time stuck high/low, 25/85 °C, 250 Hz–10 kHz | GPIO source, BAT54S with hot-leakage resistors, U14 thresholds as limits |
| `sim_hotplug.py` | Does closing the power switch violate the DRV8316's 40 V abs max or 4 V/µs VM ramp limit? LM74502 + Q7/Q8 soft-start (hysteretic EN/UVLO comparator, C18, D4, D10/C13/R32) across pack stiffness, lead inductance, C1 ESR (new/aged/cold), gate-current spread (40–77 µA), a 12 V pack, a reversed pack (with/without D10), re-close after 1 ms–1.5 s incl. the minimum-UVLO worst case, and a contact bounce under a 20 A weapon load (operating envelope ≥ 0 °C; one −40 °C case outside it) | pack R, lead L, switch, LM74502 behavioural model, Q7/Q8 VDMOS, TVS, polymer ESR/ESL, 3 bridge MLCCs, both DRV8316 VM filter branches (R302/R402 + 2 × 10 µF 1210), MLCCs with their DC-bias curves, buck as a constant-power load above its UVLO, ~66 kΩ of DC dividers, bleeder |
| `sim_weapon_bridge.py` | Weapon half-bridge overshoot vs gate-drive strength and commutation-loop inductance | VDMOS fitted to the HYG015N04LS1C2 datasheet (Ciss/Coss/Crss, Qg/Qgd, RG, trr); DRV8323 IDRIVE as a current source/sink with the gate handshake (the pre-2026-09-29 RC-gate model shot through on every edge); real supply; bridge MLCCs with DC bias (charge-integrator form) |
| `sim_fault_kick.py` | Weapon fault-clear kick at the DRV8316 VM pins (comparator trip and VDS-only trip) | pack, lead, C14, switch, TVS, C1 ESR cases, bridge MLCCs and both VM branches with DC bias, plane/ESL, fault current turned off 0.7/1.0 µs after onset |
| `sim_weapon_spinup.py` | Spin-up time, drum energy, pack current, bus sag | DC-equivalent FOC (current limit, then voltage limit), mechanics as an RC analogue |

Captured results (hotplug, bridge, fault_kick 2026-09-29, others 2026-09-23): [`hotplug.out`](hotplug.out), [`arm.out`](arm.out), [`bridge.out`](bridge.out), [`fault_kick.out`](fault_kick.out),
[`spinup.out`](spinup.out).  Conclusions are in `../DESIGN.md` §5.

Limits of these models: the FET is not a vendor model (reverse recovery is the weakest part);
motor resistance for the 2822 is an estimate; the pack is a fixed-voltage source with series R.
Use them for trends and design margins, and confirm on the bench with a scope on SHx/VDS.
