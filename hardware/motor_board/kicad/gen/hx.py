"""hx: scratch stage for placement trials (moves only)."""
import os
import v2_pre
from v2_pre import EDITS  # noqa: F401

ROT = float(os.environ.get("HX_ROT", "90"))
for ref, x, y, r, s in (("D8", 37.6, 29.2, ROT, "B"), ("D7", 40.95, 28.5, ROT, "B")):
    EDITS.append(dict(op="move", ref=ref, x=x, y=y, rot=r, side=s))
