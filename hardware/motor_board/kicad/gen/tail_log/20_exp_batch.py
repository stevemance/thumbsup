"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = []
# why SPI_SCK 29.7-U3 lifting []
EDITS += [{"op": "route", "net": "SPI_SCK", "a": ["pt", 29.7, 28.25, "In2.Cu"], "b": ["pad", "U3", "35"], "w": 0.127, "margin": 10.0, "max_ratio": 4.0, "tag": "SPI_SCK 29.7-U3"}]
# why W_EN 32.75-46.6 lifting ['W_SOC']
EDITS += [{"op": "rip", "box": [44.95, 22.0, 45.55, 24.75], "nets": ["W_SOC"], "layers": ["In2.Cu"], "reroute": {"margin": 9.0, "max_ratio": 5.0}}, {"op": "route", "net": "W_EN", "a": ["pt", 32.75, 29.05, "B.Cu"], "b": ["pt", 46.6, 24.45, "F.Cu"], "w": 0.127, "margin": 10.0, "max_ratio": 4.0, "tag": "W_EN 32.75-46.6"}]
# why +3V3 U1-31.515 lifting ['INA_nCS']
EDITS += [{"op": "rip", "box": [31.2, 32.5, 31.7, 33.0], "nets": ["INA_nCS"], "layers": ["B.Cu"], "reroute": {"margin": 9.0, "max_ratio": 5.0}}, {"op": "route", "net": "+3V3", "a": ["pad", "U1", "48"], "b": ["via", 31.515, 33.24], "w": 0.2, "margin": 10.0, "max_ratio": 4.0, "tag": "+3V3 U1-31.515"}]
