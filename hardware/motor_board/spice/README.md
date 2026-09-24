# Motor board SPICE checks

ngspice through KiCad's `libngspice` (`hardware/tools/spice/ngspice_shared.py`); no ngspice
binary needed.  Run with the hardware venv (numpy):

```
cd hardware/motor_board/spice
../../tools/.venv/bin/python sim_hotplug.py        # ~1 min
../../tools/.venv/bin/python sim_weapon_bridge.py  # ~15 min (18 cases)
../../tools/.venv/bin/python sim_weapon_spinup.py  # seconds
```

| Script | Question | Model notes |
|---|---|---|
| `sim_hotplug.py` | Does plugging in a 4S pack violate the DRV8316's 40 V abs max or 4 V/µs VM ramp limit? | pack R, lead L, TVS (fit to the SMBJ20A clamp), polymer ESR/ESL, MLCC, trace to VM |
| `sim_weapon_bridge.py` | Weapon half-bridge overshoot vs gate-drive strength and commutation-loop inductance | VDMOS fitted to the HYG015N04LS1C2 datasheet (Ciss/Coss/Crss, Qg/Qgd, RG, trr); DRV8323 IDRIVE as an 11 V edge behind Rg; loop L damped 2 Ω |
| `sim_weapon_spinup.py` | Spin-up time, drum energy, pack current, bus sag | DC-equivalent FOC (current limit, then voltage limit), mechanics as an RC analogue |

Captured results (2026-09-23): [`hotplug.out`](hotplug.out), [`bridge.out`](bridge.out),
[`spinup.out`](spinup.out).  Conclusions are in `../DESIGN.md` §5.

Limits of these models: the FET is not a vendor model (reverse recovery is the weakest part);
motor resistance for the 2822 is an estimate; the pack is a fixed-voltage source with series R.
Use them for trends and design margins, and confirm on the bench with a scope on SHx/VDS.
