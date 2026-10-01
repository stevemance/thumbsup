"""Push design/motor_board.py's MCU_PINS into a board's U1 pads (after a pin swap), in place:
    /usr/bin/python3 setpadnets.py <board.kicad_pcb> [...]
Only U1 pads whose net differs are changed; a pad's old copper stays (it now belongs to the old net, so DRC flags any
track left on a moved pin).  Prints each change."""
import re
import sys
from pathlib import Path

import pcbnew

MB = Path(__file__).resolve().parents[2]
src = (MB / "design" / "motor_board.py").read_text()
src = src[src.index("MCU_PINS = {"):]
src = src[:src.index("\n}") + 2]
PINS = {pin: net for pin, port, net in re.findall(r'"(\d+)": \("([^"]+)", "([^"]+)"', src)}

for path in sys.argv[1:]:
    b = pcbnew.LoadBoard(path)
    nets = {n.GetNetname().split("/")[-1]: n for n in b.GetNetsByName().values() if n.GetNetname()}
    fp = b.FindFootprintByReference("U1")
    for p in fp.Pads():
        want = PINS.get(p.GetNumber())
        if not want or want == "NC" or want not in nets:
            continue
        if p.GetNetname().split("/")[-1] != want:
            print(f"{Path(path).name}: U1.{p.GetNumber()} {p.GetNetname()} -> {nets[want].GetNetname()}")
            p.SetNet(nets[want])
    b.Save(path)
