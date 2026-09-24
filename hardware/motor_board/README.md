# ThumbsUp motor board

Battery in, three brushless channels out, 5 V to the compute board.  Sensorless weapon
(DRV8323RH + 6 FETs), two FOC drive motors with Hall/encoder feedback (2 × DRV8316C), one
STM32G474 running all three, 4S.  Battery input, reverse-polarity protection, pack
monitoring (INA239: V, I, P; BQ76907: per-cell voltages), a soft-start power switch and all
regulation live here.  199 JLC-assembled parts (rev L, after thirty adversarial review rounds in
[review/](review/), then a trim of the speculative firmware policy they had accumulated).

Start with [DESIGN.md](DESIGN.md).  Draw the schematic from [design/nets.md](design/nets.md)
(generated from [design/motor_board.py](design/motor_board.py)); parts in [BOM.md](BOM.md);
MCU pins in [design/mcu_pinmap.md](design/mcu_pinmap.md); SPICE checks in [spice/](spice/);
datasheets in [datasheets/](datasheets/).

```
python3 design/motor_board.py      # re-check the netlist and regenerate nets/BOM/pinmap
python3 design/calcs.py            # regenerate the sizing tables
../tools/.venv/bin/python spice/sim_hotplug.py   # etc., see spice/README.md
```
