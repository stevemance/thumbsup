#!/bin/bash
# r2/final.sh <board.kicad_pcb> : DRC (errors + unconnected split), GND count with In1 filled (copy), plane check
cd "$(dirname "$0")/.." || exit 1
B=$(realpath "$1")
W=out/r2_final; mkdir -p $W
cp ../motor_board/motor_board.kicad_pro $W/board.kicad_pro; cp ../motor_board/motor_board.kicad_dru $W/board.kicad_dru
cp "$B" $W/board.kicad_pcb
kicad-cli pcb drc --format json -o $W/drc.json $W/board.kicad_pcb > /dev/null 2>&1
python3 r2/opens.py $W/drc.json
/usr/bin/python3 r2/gndzone.py $W/board.kicad_pcb $W/board_gnd.kicad_pcb 2>&1 | grep filled
cp $W/board.kicad_pro $W/board_gnd.kicad_pro; cp $W/board.kicad_dru $W/board_gnd.kicad_dru
kicad-cli pcb drc --format json -o $W/drc_gnd.json $W/board_gnd.kicad_pcb > /dev/null 2>&1
echo "with In1 GND filled:"; python3 r2/opens.py $W/drc_gnd.json
/usr/bin/python3 planecheck.py dump $W/board.kicad_pcb --fill 2>&1 | grep dumped
uv run --no-project --with numpy --with scipy --with matplotlib python planecheck.py check > out/planecheck_r2.txt 2>&1
grep -E "minimum web|SLOT|chains with|region|pour:|piece\(s\)|KiCad" out/planecheck_r2.txt
