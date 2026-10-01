"""Wait until a log file changes (or a timeout): python3 wait_log.py <file> <timeout_min>.  Prints the new tail or
'NO UPDATE in N min' and exits.  Used to watch long agent stages."""
import sys
import time
from pathlib import Path

f, tmo = Path(sys.argv[1]), float(sys.argv[2]) * 60
m0 = f.stat().st_mtime if f.exists() else 0
t0 = time.time()
while time.time() - t0 < tmo:
    if f.exists() and f.stat().st_mtime > m0:
        time.sleep(2)
        print("\n".join(l[:600] for l in f.read_text().splitlines()[-2:]))
        sys.exit(0)
    time.sleep(10)
print(f"NO UPDATE in {tmo / 60:.0f} min")
