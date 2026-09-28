"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, margin=8.0, max_ratio=6.0)
ROT = 0
# R117 (2.2k series R, motor-R NTC line) from U1's east side into the rear band beside D8 / R53 (the R_MTEMP node):
# R_TEMPJ = J3.6 -> via (R_H1 B / R_H3B L3 lifted) -> L5 -> R117.1 (kept off R_H1's B corridor);
# R117.2 -> the R_MTEMP via at D8.  Same nets, no firmware change.
EDITS = [
    dict(op='rip', box=(61.45, 31.0, 62.35, 31.9), nets=['/sensors/R_H1'], layers=['B.Cu'], cross=True, reroute=RR),
    dict(op='rip', box=(61.45, 31.0, 62.35, 31.9), nets=['/sensors/R_H3B'], layers=['In2.Cu'], cross=True, reroute=RR),
    dict(op="rip_ref", ref="R117"),
    dict(op="move", ref="R117", x=53.0, y=30.7, rot=ROT, side="B"),
    dict(op='via', c=(61.9, 31.45), net='/sensors/R_TEMPJ', d=0.4, drill=0.2),
    dict(op='route', net='/sensors/R_TEMPJ', a=('pad', 'J3', '6'), b=('via', 61.9, 31.45), layers=['B.Cu'], w=0.15, margin=1.5, max_ratio=4.0),
    dict(op='route', net='/sensors/R_TEMPJ', a=('pad', 'R117', '1'), b=('via', 61.9, 31.45), layers=['B.Cu', 'In4.Cu', 'In3.Cu'], layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, w=0.15, margin=4.0, max_ratio=5.0, avoid=[['B.Cu', 58.5, 30.3, 62.6, 32.6, 'tracks']]),
    dict(op='route', net='R_MTEMP', a=('pad', 'R117', '2'), b=('via', 51.4, 32.25), layers=['B.Cu'], w=0.15, margin=3.0, max_ratio=5.0),
]
