"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why."""

L4 = "In3.Cu"
# INH pair diagonals y = x - c (INHA, INHB): c0 south-east of the jogs (room for R_MTEMP's via by R117), c north-west
# of them (clear of W_SOB's hop via at (40.3, 20.0)); each line jogs 0.75 mm SW at y = J, INHB first (its old line is
# vacant where INHA's jog crosses it)
CA0, CB0, CA, CB, JA, JB = 20.655, 20.23, 19.6, 19.175, 21.3, 22.0
U1_L4 = [L4, 28.8, 21.35, 41.9, 32.6]         # U1 on L4 below its top via row: kept for the nets that must cross U1

EDITS = [
    # U1's east via column: the two +3V3A fan-out vias (pins 28/29) are not needed (+3V3A is bottom-local: C65, C66,
    # C71, R60 right beside the pins) and they narrow the only L4 gap in the column; the pins tie to C65 on B instead
    dict(op="rip", box=(39.6, 26.95, 41.3, 28.1), nets=["/mcu/+3V3A"]),
    dict(op="route", net="/mcu/+3V3A", a=("pad", "U1", "28"), b=("pad", "C65", "1"), layers=["B.Cu"], w=0.25, margin=2.0),
    dict(op="rip", box=(42.85, 26.65, 43.05, 26.9), nets=["GND"], layers=["B.Cu"]),
    # C66.1 (bulk) into C71.1 on B, between C65.2 and the GND stitch vias
    dict(op="track", net="/mcu/+3V3A", layer="B.Cu", w=0.2, pts=[(43.175, 25.5), (43.52, 25.85), (43.52, 26.8), (43.97, 27.25)]),
    dict(op="route", net="/mcu/+3V3A", a=("pad", "U1", "29"), b=("pad", "U1", "28"), layers=["B.Cu"], w=0.25, margin=1.0),
    # U2 rear bus INH lines: INHB ran through U1's field (fencing its east gap) and INHA looped south of INHB's via.
    # Both re-laid by hand as a pair tucked under the INL bundle (45 deg, y = x - 21.15 near U1): INHA 0.35 off it,
    # INHB 0.3 further in, then rows west into their vias (INHA y 18.45, INHB y 19.45, clear of W_SOA's escape via;
    # INHB ends first).  What sat on the pair's path is lifted and re-laid after it: two GND drop vias (re-dropped),
    # W_SOB's hop via, R_SOC's via, W_nFAULT's L4 loop, R_MTEMP's L4 run.
    dict(op="rip", box=(29.0, 17.5, 50.4, 33.5), nets=["W_INHB"], layers=[L4]),
    dict(op="rip", box=(30.0, 21.5, 42.0, 31.0), nets=["W_INHB"]),
    dict(op="rip", box=(33.5, 17.5, 50.4, 27.6), nets=["W_INHA"], layers=[L4], keep_vias=True),
    dict(op="rip", box=(32.0, 17.5, 39.0, 22.0), nets=["W_nFAULT"], layers=[L4]),
    dict(op="rip", box=(38.4, 17.5, 43.9, 22.0), nets=["W_nFAULT"], layers=["F.Cu", "B.Cu"]),
    dict(op="rip", box=(38.4, 18.4, 38.9, 18.9), nets=["W_nFAULT"]),
    dict(op="rip", box=(43.5, 24.0, 46.0, 33.0), nets=["R_MTEMP"], layers=[L4]),
    dict(op="rip", box=(43.8, 24.1, 44.3, 24.6), nets=["R_MTEMP"]),
    dict(op="rip", box=(48.1, 27.1, 48.5, 27.5), nets=["GND"]),
    dict(op="rip", box=(44.6, 24.5, 45.0, 24.9), nets=["GND"]),
    dict(op="rip", box=(44.7, 26.15, 44.9, 26.35), nets=["GND"]),
    # R_SOC's west end (F along y 24.9 from R82, hop to B at (45.8, 25.9)) is lifted: its hop via sat on INHB and the
    # F run fenced the only via spot for R_MTEMP south-west of the pair; re-routed after R_MTEMP
    dict(op="rip", box=(41.5, 24.5, 53.7, 31.35), nets=["R_SOC"]),
    dict(op="track", net="W_INHA", layer=L4, w=0.15,
         pts=[(50.625, 27.3), (27.3 + CA0, 27.3), (JA + CA0, JA), (JA + CA0 - (CA0 - CA) / 2, JA + (CA0 - CA) / 2),
              (18.45 + CA, 18.45), (35.45, 18.45), (35.3, 18.6)]),
    dict(op="track", net="W_INHB", layer=L4, w=0.15,
         pts=[(50.7, 27.95), (27.95 + CB0, 27.95), (JB + CB0, JB), (JB + CB0 - (CB0 - CB) / 2, JB + (CB0 - CB) / 2),
              (19.45 + CB, 19.45), (35.95, 19.45), (35.8, 19.3)]),
    # R_MTEMP R117.2 -> R53.2: via just SW of R117 (between the pair and C66), L4 down west of the C66/C71 GND vias
    dict(op="track", net="R_MTEMP", layer="B.Cu", w=0.15, pts=[(43.425, 23.7), (44.05, 24.325), (44.05, 24.6)]),
    dict(op="via", net="R_MTEMP", c=(44.05, 24.6)),
    dict(op="track", net="R_MTEMP", layer=L4, w=0.15,
         pts=[(44.05, 24.6), (43.45, 25.2), (43.45, 27.6), (44.75, 28.9), (44.75, 32.4)]),
    dict(op="route", net="R_SOC", a=("pad", "R82", "1"), b=("via", 53.75, 31.3), w=0.15, margin=6.0,
         layers=["F.Cu", "B.Cu", L4]),
    dict(op="route", net="W_nFAULT", a=("pad", "TP9", "1"), b=("via", 32.5, 21.55), w=0.15, margin=6.0),
    # L_TEMPJ (J2.6 -> R113) and R_S1 (U10 -> U1.51) through the east gap
    dict(op="rip", box=(32.5, 0, 57, 35), nets=["R_S1"]),
    dict(op="route", net="/sensors/L_TEMPJ", a=("via", 36.2, 29.6), b=("pad", "R113", "1"), margin=6.0, w=0.15,
         layers=["F.Cu", "B.Cu", L4]),
    dict(op="route", net="R_S1", a=("pad", "U10", "7"), b=("pad", "U1", "51"), margin=8.0, w=0.15),
]
