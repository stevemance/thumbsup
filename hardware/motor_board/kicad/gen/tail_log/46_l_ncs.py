"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.2}, margin=8.0, max_ratio=8.0)
# L_nCS (U1.41): via at the inner end of the pin's pad (filled + capped, FAB.md), L3 west to the U3 stub; R_S2 L4,
# SPI_MISO L3 and a SPI_MOSI L3 piece lifted and re-laid
EDITS = [
    dict(op='rip', box=(34.8, 30.0, 35.7, 30.9), nets=['R_S2'], layers=['In3.Cu'], cross=True, reroute=RR),
    dict(op='rip', box=(34.7, 30.8, 35.8, 31.7), nets=['SPI_MISO'], layers=['In2.Cu'], cross=True, reroute=RR),
    dict(op='rip', box=(29.6, 30.2, 30.4, 32.3), nets=['SPI_MOSI'], layers=['In2.Cu'], cross=True, reroute=RR),
    dict(op='via', c=(35.25, 31.25), net='L_nCS', d=0.4, drill=0.2),
    dict(op='track', pts=[(35.25, 31.675), (35.25, 31.25)], layer='B.Cu', net='L_nCS', w=0.15),
    dict(op='route', net='L_nCS', a=('via', 35.25, 31.25), b=('pt', 28.2, 30.25, 'F.Cu'), layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.3, 'In2.Cu': 1.5}, w=0.15, margin=4.0, max_ratio=4.0),
]
