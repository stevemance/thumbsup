"""hS: silkscreen for JLC (kicad/gen/silk.py).  Silk only on parts someone handles after assembly: connectors and wire
holes (J, JBAT, JW, JL, JR), solder jumpers (JP), test pads (TP), mounting holes (MH), the status LED (D3) and C1 (staked
by hand).  Every other part's silk outline moves to its Fab layer and its reference is hidden.  Orientation-sensitive
parts (ICs, diodes, FETs) get a pin-1 / cathode dot, since JLC checks placement polarity against the silk.  Function
labels: wire names on the bottom (where the wires are soldered; top labels sat ambiguously between holes), battery
polarity on both sides; they replace the JBAT/JW/JL/JR references, J4 B- / B4+, J2 / J3 VS / T ends, JP1 / JP2 3V3 (1-2, default)
and 5V (2-3) sides (DESIGN 3.4, 6.9)."""
import v2_pre
from v2_pre import EDITS

v2_pre.VIA_PITCH = 0.9

# (label, wire hole, preferred side: degrees, 0 = +x, 90 = +y = toward the rear) - toward the board inside
WIRES = [("BAT+", "JBAT1", 90), ("BAT-", "JBAT2", 0), ("WA", "JW1", 90), ("WB", "JW2", 90), ("WC", "JW3", 90),
         ("LA", "JL1", 0), ("LB", "JL2", 0), ("LC", "JL3", 0), ("RA", "JR1", 270), ("RB", "JR2", 270), ("RC", "JR3", 270)]
EDITS.append(dict(
    op="silk",
    keep=r"(J|JBAT|JW|JL|JR|JP|TP|MH)\d+|D3|C1",
    mark=r"(U|D|Q)\d+",
    hide_ref=[r for _, r, _ in WIRES] + ["MH1", "MH2", "MH3", "MH4"],
    labels=[(s, r, 1, "FB" if s.startswith("BAT") else "B", a) for s, r, a in WIRES] + [
        ("B-", "J4", 1, "F"), ("B4+", "J4", 5, "F"),
        ("VS", "J2", 1, "F"), ("T", "J2", 6, "F"), ("VS", "J3", 1, "F"), ("T", "J3", 6, "F"),
        ("3V3", "JP1", 1, "F"), ("5V", "JP1", 3, "F"), ("3V3", "JP2", 1, "F"), ("5V", "JP2", 3, "F")]))
