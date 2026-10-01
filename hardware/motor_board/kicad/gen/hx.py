"""hx: scratch stage for placement trials (moves only)."""
import os
import v2_pre
from v2_pre import EDITS  # noqa: F401

ROT = float(os.environ.get("HX_ROT", "90"))
EDITS.append(dict(op="move", ref="U6", x=61.75, y=30.25, rot=ROT, side="B"))
