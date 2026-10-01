"""hS: silkscreen for JLC.  Silk only on parts someone handles after assembly: connectors and wire holes (J, JBAT, JW,
JL, JR), solder jumpers (JP), test pads (TP), mounting holes (MH), the status LED (D3) and C1 (staked by hand).  Every
other part's silk outline moves to its Fab layer and its reference is hidden; board-level silk text (wire names) stays."""
import v2_pre
from v2_pre import EDITS

v2_pre.VIA_PITCH = 0.9

EDITS.append(dict(op="silk", keep=r"(J|JBAT|JW|JL|JR|JP|TP|MH)\d+|D3|C1"))
