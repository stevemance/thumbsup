# Generated capture for the motor-board KiCad project

Scripts that produced `../motor_board/*.kicad_sch` (labels-on-pins schematic) and the rough
`../motor_board/motor_board.kicad_pcb` placement, from `design/motor_board.py` + `design/netlist.csv`.

* `blocks.py`: which parts form each circuit block on each sheet (schematic grouping and PCB clusters).
* `gen_sch.py`: rebuilds the six sub-sheets. **Overwrites them** (backup in `out/sch_backup/` on first run). ~2-3 min.
* `check_nets.py`: exports the netlist with kicad-cli and compares every net, pin by pin, with `design/netlist.csv`.
* `build_pcb.py` (run with `/usr/bin/python3`, KiCad's pcbnew): **overwrites** `motor_board.kicad_pcb` with a
  fresh board. It keeps the project file but writes placeholder JLC rules into it. Only for the initial
  placement: once you have moved parts or routed anything, don't rerun it. Use Update PCB from Schematic instead.

Close KiCad before running any of them.
