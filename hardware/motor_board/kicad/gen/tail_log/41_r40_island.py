"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# R40.2 (W_EN pull-down) sat on a B GND fill island fenced by W_EN: lift that W_EN run off B there
EDITS = [dict(op='rip', box=(20.66, 24.33, 22.92, 26.6), nets=['W_EN'], layers=['B.Cu'], cross=True,
              reroute=dict(layers=['F.Cu', 'B.Cu', 'In3.Cu', 'In2.Cu', 'In4.Cu'], layer_cost={'In4.Cu': 1.0}, margin=12.0, max_ratio=8.0, avoid=[['B.Cu', 21.16, 24.83, 22.42, 26.1, 'tracks']]))]
