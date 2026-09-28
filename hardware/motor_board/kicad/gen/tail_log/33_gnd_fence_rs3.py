"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# a GND fill island merged: island B.Cu (42.13, 27.83, 43.89, 29.27): lift R_S3 off B.Cu (re-laid around the island)
EDITS = [dict(op='rip', box=(41.63, 27.33, 44.39, 29.77), nets=['R_S3'], layers=['B.Cu'], cross=True,
              reroute=dict(layers=['F.Cu', 'B.Cu', 'In3.Cu', 'In2.Cu', 'In4.Cu'], layer_cost={'In4.Cu': 1.5}, margin=9.0, max_ratio=6.0, avoid=[['B.Cu', 42.13, 27.83, 43.89, 29.27, 'tracks']]))]
