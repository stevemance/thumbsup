"""hR: board <-> regenerated schematic (2026-10-01 review decisions): every footprint re-linked to its new symbol UUID,
U7 value/fields -> INA239AQDGSRQ1 (C4367136), C117 (100 nF, BMS_BAT bypass at U8.16/17) added.  C117's spot here is
provisional (nearest courtyard-free 0603 spot to U8.16, ~3.5 mm); the U2 / buck re-place frees room at the pins."""
import v2_pre
from v2_pre import EDITS, P, route

v2_pre.VIA_PITCH = 0.9

EDITS.append(dict(op="sync", place={"C117": (75.7, 18.5, 270, "B")}))
route("BMS_BAT", P("C117", 1), ("via", 73.0, 21.15), margin=4.0)
