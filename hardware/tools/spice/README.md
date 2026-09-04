# SPICE checks for the ThumbsUp board

Small ngspice simulations that verify specific parts of the power path. They use
KiCad's shared ngspice library (`/usr/lib/x86_64-linux-gnu/libngspice.so.0`) through
a self-contained ctypes wrapper, so **no `ngspice` binary or PySpice/InSpice is needed**.

## Run

```bash
cd hardware/tools/spice
PY=../.venv/bin/python           # venv only needs numpy
$PY ngspice_shared.py            # self-test (resistor divider)
$PY sim_rpp.py                   # reverse-polarity P-FET, prompt configuration
$PY sim_rpp.py --rgs 100k        # same with the schematic's extra 100k gate-source resistor
$PY sim_en_uvlo.py               # AP63205 EN divider UVLO thresholds
$PY sim_bootstrap.py             # FD6288 bootstrap droop, Cboot 100 nF and 1 uF (~6 s)
```

Set `NGSPICE_LIB=/path/to/libngspice.so` if the library is elsewhere.

## Files

| file | what |
|---|---|
| `ngspice_shared.py` | ctypes binding: `NgSpice().load_netlist(str)`, `.run("dc ...")`, `.vector("v(node)")` -> numpy |
| `sim_rpp.py` | DC sweep -13..+13 V of the AP40P05 RPP FET in both orientations (level-1 PMOS + explicit body diode + 12 V G-S zener) |
| `sim_en_uvlo.py` | AP63205 EN pin (1.5 uA always + 4 uA when ON, 1.18/1.10 V thresholds): DC sweeps + transient with hysteretic switch |
| `sim_bootstrap.py` | VB-VS droop with 4 nF gate charged from Cboot once per 24 kHz / 95 % cycle, IQBS = 270 uA |

## Models

Generic models only (no vendor SPICE models were available offline):
* P-FET: `PMOS level=1 vto=-1.5 kp=6` (Rds(on) ~20 mohm at Vgs=-10 V), body diode added explicitly.
* Zener: `D bv=12 ibv=5m`.  Schottky: common 1N5819 library model (Vf ~0.3-0.4 V).
* FD6288 high-side driver: ideal 2 ohm switches, IQBS from the FD6288Q datasheet (270 uA max).
