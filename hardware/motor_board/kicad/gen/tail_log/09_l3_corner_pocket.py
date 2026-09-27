"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
from tail_auto import auto  # noqa: E402

EDITS = [
    # L3 VBAT feed trimmed in the south-west: its x 21-34.6 / y 16.5-20.8 corner and x 21-26 / y 10.2-16.5 carried no
    # pack current (C1 is fed by the L1 pack pour; the feed's stitching vias stay: all at y <= 15.8), and they walled the
    # U7 / J1 / U1-north signals off L3
    dict(op="outline", name="L3 VBAT feed", poly=[(21.0, 1.5), (34.6, 1.5), (34.6, 6.0), (72.8, 6.0), (72.8, 18.2),
                                                  (34.6, 18.2), (34.6, 16.5), (26.0, 16.5), (26.0, 10.2), (21.0, 10.2)]),
]
EDITS += [
    # L_VM: the left drive's second bulk cap C310 was isolated; a via beside it, L3 (the freed corner) to L_VM's via
    dict(op="via", net="/drive_left/L_VM", c=(25.75, 17.3), d=0.6, drill=0.3),
    dict(op="track", net="/drive_left/L_VM", layer="B.Cu", w=0.4, pts=[(26.025, 17.85), (25.75, 17.3)]),
    dict(op="route", net="/drive_left/L_VM", a=("via", 25.75, 17.3), b=("via", 22.0, 22.6), w=0.4, margin=3.0, layers=[L3]),
]
# the pocket west of U1: W_ARM_S / W_INLC_M / L_S3 ran east-west on L3 through it and fenced both the SPI legs north to
# U7 and the U3 bottom-row trio; lifted, the fenced nets go first, the three re-route after (any layer)
EDITS += [dict(op="rip", box=(24.0, 21.5, 31.2, 27.2), nets=["W_ARM_S", "W_INLC_M"], layers=[L3]),
          dict(op="rip", box=(28.3, 23.0, 33.2, 26.2), nets=["L_S3"], layers=[L3]),
          dict(op="rip", box=(28.4, 25.8, 30.2, 27.2), nets=["L_S3"])]     # U9.2's F stub to the old west via
_S = dict(w=0.15, margin=7.0)
POCKET3 = [L3, 23.0, 22.75, 29.25, 34.0]      # south of U1's left-column targets: for the U3 trio and the SPI legs only
EDITS += [dict(op="route", net="W_ARM_S", a=("via", 25.65, 21.95), b=("via", 31.4, 26.75), avoid=[POCKET3], **_S),
          dict(op="route", net="W_INLC_M", a=("via", 26.25, 22.35), b=("pt", 31.5, 25.8, L3), avoid=[POCKET3], **_S),
          dict(op="route", net="L_INHC", a=("via", 25.25, 33.2), b=("via", 28.4, 23.1), layers=[L3], margin=4.0, w=0.15),
          dict(op="route", net="L_INHA", a=("via", 23.25, 33.2), b=("via", 28.72, 24.75), layers=[L3], margin=4.0, w=0.15),
          dict(op="route", net="L_nFAULT", a=("pad", "U3", "22"), b=("via", 27.35, 24.25), margin=4.0, w=0.15),
          dict(op="route", net="SPI_MOSI", a=("via", 27.6, 27.2), b=("pad", "U7", "2"), **_S),
          dict(op="route", net="SPI_MISO", a=("via", 27.75, 27.9), b=("pad", "U7", "4"), **_S),
          dict(op="route", net="SPI_SCK", a=("via", 28.25, 28.25), b=("pad", "U7", "5"), **_S)]
