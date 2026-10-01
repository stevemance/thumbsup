#!/bin/bash
# place + dump + views:  r2/pl.sh [x0 y0 x1 y1 layers name] ...   (run from kicad/v2)
cd "$(dirname "$0")/.." || exit 1
timeout 900 /usr/bin/python3 place.py 2>&1 | grep -v -e property.h -e Debug | tail -12
/usr/bin/python3 r2/view.py dump ../motor_board/motor_board.kicad_pcb out/r2v_place.json 2>&1 | tail -1
while [ $# -ge 6 ]; do
  uv run --no-project --with matplotlib python r2/view.py plot out/r2v_place.json "$1" "$2" "$3" "$4" "out/r2v_$6.png" "$5" 2>&1 | tail -1
  shift 6
done
