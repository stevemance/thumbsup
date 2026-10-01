#!/bin/bash
# run one tail.py stage:  r2/stage.sh <exp> <base exp | "proj">   (from anywhere)
GEN="$(cd "$(dirname "$0")/../../gen" && pwd)"
if [ "$2" = "proj" ]; then
  BASE="$(cd "$GEN/../motor_board" && pwd)/motor_board.kicad_pcb"
else
  BASE="$GEN/out/exp/$2/proj/motor_board.kicad_pcb"
fi
cd "$GEN" || exit 1
mkdir -p "$GEN/out/exp/$1/proj" && cp "$GEN/../motor_board/motor_board.kicad_dru" "$GEN/out/exp/$1/proj/"
TAIL_EXP="$1" TAIL_BASE="$BASE" timeout 3600 /usr/bin/python3 tail.py 2>&1 | grep -v -e property.h -e Debug -e "^ok "
/usr/bin/python3 "$GEN/geom_export.py" "$GEN/out/exp/$1/proj/motor_board.kicad_pcb" "$GEN/out/exp/$1/geom_r2.json" 2>&1 | tail -1
