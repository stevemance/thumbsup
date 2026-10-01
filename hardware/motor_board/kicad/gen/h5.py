"""h5: r2_fix's closing pass (wide windows, necked rails, retry) on top of h4."""
import os

os.environ["R2_BASE"] = os.environ.get("H5_BASE", "h4")
import r2_fix  # noqa: F401,E402
from v2_pre import EDITS  # noqa: F401,E402
