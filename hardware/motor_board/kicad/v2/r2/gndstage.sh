#!/bin/bash
# r2_gnd stage on the existing gndvias board (out/exp/r2_gv/board.kicad_pcb, made by r2/gnd.sh from r2_main)
GEN="$(cd "$(dirname "$0")/../../gen" && pwd)"
cd "$GEN" || exit 1
mkdir -p out/exp/r2_gnd/proj && cp ../motor_board/motor_board.kicad_dru out/exp/r2_gnd/proj/
TAIL_EXP=r2_gnd TAIL_BASE="$GEN/out/exp/r2_gv/board.kicad_pcb" timeout 3000 /usr/bin/python3 tail.py 2>&1 | grep -E "DRC|^    |router req"
/usr/bin/python3 geom_export.py out/exp/r2_gnd/proj/motor_board.kicad_pcb out/exp/r2_gnd/geom_r2.json | tail -1
