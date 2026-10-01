#!/bin/bash
# r2/views.sh <exp> x0 y0 x1 y1 tag  : dump the stage board and plot F, L3, B views with its opens
cd "$(dirname "$0")/.." || exit 1
/usr/bin/python3 r2/view.py dump ../gen/out/exp/$1/proj/motor_board.kicad_pcb out/r2v_$1.json 2>/dev/null | tail -1
for L in F L3 B; do
  uv run --no-project --with matplotlib python r2/view.py plot out/r2v_$1.json $2 $3 $4 $5 out/r2v_$6_$L.png $L ../gen/out/exp/$1/drc.json 2>&1 | tail -1
done
