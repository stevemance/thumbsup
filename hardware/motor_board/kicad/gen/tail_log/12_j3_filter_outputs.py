"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

B = "B.Cu"
GV = [(53.755, 33.15), (56.7, 33.35), (58.45, 32.95), (58.545, 33.35), (58.86, 32.515), (58.45, 32.4), (58.65, 32.05),
      (55.5, 31.25)]
EDITS = [
    # right-sensor filter outputs (R115.2 H2B, R116.2 H3B) had no way east past J3's links: they drop to vias under the
    # connector body (H3B beside J3.6, H2B between J3.5 / J3.4) and run east on L3 south of the bus to C115 / C116 / U10.
    # For them: R_H1's pull-up lane re-laid at y 31.85, R_S1's L4->L3 hop moved east of them and its L3 lane down to y 32.75,
    # R_SOC's dangling hop via lifted, GND stitching vias in the strip lifted (J3.2 and C408.2 get placed ones, the rest
    # re-drop)
    dict(op="rip", box=(52.7, 31.1, 53.1, 31.5), nets=["R_S1"]),
    dict(op="rip", box=(53.5, 31.1, 54.0, 31.5), nets=["R_SOC"]),
    dict(op="rip", box=(49.0, 30.02, 54.6, 33.0), nets=["/sensors/R_H1"], layers=[B]),
]
EDITS += [dict(op="rip", box=(x - 0.05, y - 0.05, x + 0.05, y + 0.05), nets=["GND"]) for x, y in GV]
EDITS += [
    dict(op="track", net="/sensors/R_H1", layer=B, w=0.15,
         pts=[(54.5, 30.5), (54.5, 31.5), (54.15, 31.85), (49.65, 31.85), (49.5, 32.0), (49.5, 32.45), (49.05, 32.9),
              (49.01, 32.95)]),
    dict(op="track", net="R_S1", layer=L4, w=0.15, pts=[(55.45, 28.75), (53.6, 30.6), (53.6, 32.6)]),
    dict(op="via", net="R_S1", c=(53.6, 32.6)),
    dict(op="track", net="R_S1", layer=L3, w=0.15,
         pts=[(53.6, 32.6), (53.45, 32.75), (50.35, 32.75), (49.6, 32.0), (48.9, 31.3), (45.1, 31.3)]),
    dict(op="track", net="/sensors/R_H3B", layer=B, w=0.15,
         pts=[(50.49, 28.2), (50.95, 28.66), (50.95, 30.95), (51.3, 31.3), (51.3, 31.35)]),
    dict(op="via", net="/sensors/R_H3B", c=(51.3, 31.35)),
    dict(op="track", net="/sensors/R_H3B", layer=L3, w=0.15,
         pts=[(51.3, 31.35), (52.05, 32.1), (55.4, 32.1), (56.25, 32.95), (59.0, 32.95)]),
    dict(op="track", net="/sensors/R_H2B", layer=B, w=0.15, pts=[(52.49, 28.2), (52.49, 28.52), (53.0, 29.03), (53.0, 31.3)]),
    dict(op="via", net="/sensors/R_H2B", c=(53.0, 31.3)),
    dict(op="track", net="/sensors/R_H2B", layer=L3, w=0.15, pts=[(53.0, 31.3), (53.15, 31.45), (55.8, 31.45), (56.17, 31.82), (59.0, 31.82)]),
    # placed GND vias: J3.2 into D2's GND pad below it (filled via-in-pad), C408.2 beside J3's right mounting pad
    dict(op="track", net="GND", layer=B, w=0.25, pts=[(55.5, 30.5), (55.5, 32.9), (55.0, 33.4)]),
    dict(op="via", net="GND", c=(55.0, 33.4)),
    dict(op="track", net="GND", layer=B, w=0.3, pts=[(59.0, 32.0), (58.3, 32.5)]),
    dict(op="via", net="GND", c=(58.3, 32.5)),
]
_S = dict(w=0.15, margin=4.0)
EDITS += [dict(op="route", net="/sensors/R_H2B", a=("pt", 59.0, 31.82, L3), b=("pad", "C115", "1"), **_S),
          dict(op="route", net="/sensors/R_H3B", a=("pt", 59.0, 32.95, L3), b=("pad", "C116", "1"), **_S),
          dict(op="route", net="/sensors/R_H3B", a=("pad", "C116", "1"), b=("pad", "U10", "6"), w=0.15, margin=5.0)]
