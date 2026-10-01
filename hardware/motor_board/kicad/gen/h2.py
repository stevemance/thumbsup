"""h2: r2_main's router flow (rip-up/reroute, U2 rear gate fan-out explicit) on top of h1 (sensor timer swap + the
hand-placed MCU escapes).  A measurement stage: how much of the 41-open result came from the old pin map."""
import os

os.environ.setdefault("R2_BASE", "h1")
import r2_main  # noqa: F401,E402  (appends its edits to v2_pre.EDITS)
from v2_pre import EDITS  # noqa: F401,E402
