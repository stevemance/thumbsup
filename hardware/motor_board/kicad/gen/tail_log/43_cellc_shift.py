"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# Undo the grow's split of the weapon bridge: cell C (Q5 / Q6 / RS3 / C31 / JW3 / NT3 / R26 / R27) moves +10 mm east,
# back beside cell B and U2 (their pre-grow relative position).  Its pours and stitching vias move with it; its gate /
# sense / phase nets take their pre-grow copper back (frozen/pregrow.kicad_pcb, the board before 0d00345, +10 mm).
# Lanes laid through the gap after the grow are lifted and re-routed; W_VC (divider -> MCU, west) is re-laid.
ALL = ['F.Cu', 'B.Cu', 'In2.Cu', 'In4.Cu', 'In3.Cu']
RR = dict(layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, margin=10.0, max_ratio=8.0)
CELL_NETS = ["/weapon/W_C", "/weapon/W_GHC", "/weapon/W_GLC", "/weapon/W_SNC", "/weapon/W_SLC"]
DEST = (46.9, -1.0, 58.6, 19.6)
EDITS = [
    dict(op='rip', box=DEST, nets=['W_SOB'], cross=True, reroute=RR),
    dict(op='rip', box=(43.0, 0.0, 60.0, 19.6), nets=['W_VB'], cross=True),
    dict(op='rip', box=DEST, nets=['W_NTC'], layers=['In3.Cu'], cross=True, reroute=RR),
    dict(op='rip', box=(0.0, 0.0, 85.0, 35.0), nets=['W_VC']),
    dict(op='rip', box=(58.6, 12.0, 60.0, 21.0), nets=['W_VA'], cross=True, reroute=RR),
    # the bottom part keep-out for the cells' gate / sense vias now starts at cell C's new west edge
    dict(op='outline', name='keepout: weapon gate/sense via corridor (bottom, parts)', poly=[(44.4, 8.5), (80.5, 8.5), (80.5, 19.0), (44.4, 19.0)]),
    dict(op="shift", refs=["Q5", "Q6", "RS3", "C31", "JW3", "NT3", "R26", "R27"], dx=10.0,
         box=[(34.4, -1.0, 47.96, 13.12), (34.4, 13.12, 47.14, 18.8)],
         nets=[], stitch=["VBAT", "GND"], zones=["cell C:", "keepout: JW3.1"]),
    dict(op="copy_nets", src="frozen/pregrow_cellc.json", nets=CELL_NETS, dx=10.0),
    dict(op='route', net='W_VC', a=('pad', 'R26', '2'), b=('pad', 'R27', '1'), layers=['B.Cu'], w=0.15, margin=2.0, max_ratio=3.0),
    dict(op='route', net='W_VC', a=('pad', 'R27', '1'), b=('pad', 'C43', '1'), layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, w=0.15, margin=6.0, max_ratio=3.0),
    dict(op='route', net='W_VC', a=('pad', 'C43', '1'), b=('pad', 'U1', '14'), layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, w=0.15, margin=4.0, max_ratio=3.0),
    dict(op='route', net='W_VB', a=('pad', 'R24', '2'), b=('pad', 'C42', '1'), layers=ALL, layer_cost={'In4.Cu': 1.0, 'In3.Cu': 1.5}, w=0.15, margin=6.0, max_ratio=3.0),
    dict(op='route', net='W_VB', a=('pad', 'R25', '1'), b=('pad', 'R24', '2'), layers=['B.Cu', 'In4.Cu'], w=0.15, margin=2.0, max_ratio=4.0),
]
