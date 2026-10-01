"""Watchdog for a Freerouting trial (fr_trial.py): prints each finished pass, any failure, a stall warning, and a
final FINISHED / FAILED line, then exits.  python3 fr_watch.py <route log name> <import log name> [stall_min]"""
import re
import sys
import time
from pathlib import Path

F = Path(__file__).resolve().parent / "out" / "fr"
route_log, import_log = F / sys.argv[1], F / sys.argv[2]
stall = float(sys.argv[3]) * 60 if len(sys.argv) > 3 else 720
start = time.time()
while not (F / "fr.log").exists():
    time.sleep(5)
    if time.time() - start > 600:
        print("FAILED: Freerouting never started (no fr.log after 10 min)", flush=True)
        sys.exit(1)
seen, last, warned = 0, time.time(), False
while True:
    log = (F / "fr.log").read_text(errors="replace")
    passes = [l for l in log.splitlines() if "pass #" in l]
    for l in passes[seen:]:
        m = re.search(r"pass #(\d+).*?in ([\d.]+) seconds.*?\((\d+) unrouted", l)
        print(f"pass {m.group(1)}: {m.group(3)} unrouted ({float(m.group(2)):.0f} s)" if m else l[:160], flush=True)
    if len(passes) > seen:
        seen, last, warned = len(passes), time.time(), False
    for f in (route_log, import_log):
        if f.exists():
            txt = f.read_text(errors="replace")
            if "Traceback" in txt or "TimeoutExpired" in txt:
                tail = [l for l in txt.splitlines() if l.strip()][-1]
                print(f"FAILED in {f.name}: {tail[:200]}", flush=True)
                sys.exit(1)
    opens = F / "opens.txt"
    if opens.exists() and opens.stat().st_size and opens.stat().st_mtime > (F / "fr.log").stat().st_mtime - 5:
        print("FINISHED: " + opens.read_text().splitlines()[0], flush=True)
        sys.exit(0)
    if time.time() - last > stall and not warned:
        print(f"STALL: no Freerouting progress for {stall / 60:.0f} min (after pass {seen})", flush=True)
        warned = True
    time.sleep(20)
