#!/bin/bash
# GND stage on top of a routed stage:  r2/gnd.sh <exp>   (from kicad/v2)
cd "$(dirname "$0")/.." || exit 1
GEN=$(cd ../gen && pwd)
SRC=$GEN/out/exp/$1/proj/motor_board.kicad_pcb
mkdir -p $GEN/out/exp/r2_gv
/usr/bin/python3 gndvias.py $SRC $GEN/out/exp/r2_gv/board.kicad_pcb 2>&1 | grep "GND stitch" | tee out/r2_gndvias.log
sed -n 's/.*without a spot: \[\(.*\)\]/\1/p' out/r2_gndvias.log | tr -d "',[]" > out/r2_gnd_missed.txt
/usr/bin/python3 planecheck.py dump $GEN/out/exp/r2_gv/board.kicad_pcb --fill 2>&1 | grep dumped
/usr/bin/python3 $GEN/geom_export.py $GEN/out/exp/r2_gv/board.kicad_pcb $GEN/out/exp/r2_gv/geom_r2.json | tail -1
uv run --no-project --with numpy --with matplotlib python r2/stitch.py r2_gv ${MIN_AREA:-1.0} ${NEED:-2}
cd $GEN && TAIL_EXP=r2_gnd TAIL_BASE=$GEN/out/exp/r2_gv/board.kicad_pcb timeout 3600 /usr/bin/python3 tail.py 2>&1 | grep -E "DRC|FAIL|^    |router req"
/usr/bin/python3 $GEN/geom_export.py $GEN/out/exp/r2_gnd/proj/motor_board.kicad_pcb $GEN/out/exp/r2_gnd/geom_r2.json | tail -1
