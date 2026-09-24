# ThumbsUp motor board

Battery in, three brushless channels out, 5 V to the compute board.  Sensorless weapon
(DRV8323RS + 6 FETs), two FOC drive motors with Hall/encoder feedback (2 × DRV8316R), one
STM32G474 running all three, 4S.  Battery input, reverse-polarity protection, pack
monitoring (INA229: V, I, energy, mAh; BQ76907: per-cell voltages and balancing) and all
regulation live here.  113 JLC-assembled parts.

Start with [DESIGN.md](DESIGN.md).  Draw the schematic from [design/nets.md](design/nets.md)
(generated from [design/motor_board.py](design/motor_board.py)); parts in [BOM.md](BOM.md);
MCU pins in [design/mcu_pinmap.md](design/mcu_pinmap.md); SPICE checks in [spice/](spice/);
datasheets in [datasheets/](datasheets/).

```
python3 design/motor_board.py      # re-check the netlist and regenerate nets/BOM/pinmap
python3 design/calcs.py            # regenerate the sizing tables
../tools/.venv/bin/python spice/sim_hotplug.py   # etc., see spice/README.md
```
