#!/usr/bin/env python3
"""Mutation test for check_lib.py: every planted library error must make it exit 1, and the
unmodified library must pass.  Run after changing check_lib.py or build_lib.py:

    python3 test_check_lib.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # hardware/motor_board
WORK = Path(tempfile.mkdtemp(prefix="check_lib_mut_")) / "motor_board"


def fresh():
    if WORK.parent.exists():
        shutil.rmtree(WORK.parent)
    (WORK / "kicad").mkdir(parents=True)
    shutil.copytree(SRC / "design", WORK / "design")
    shutil.copytree(SRC / "kicad" / "lib_build", WORK / "kicad" / "lib_build")
    return WORK / "kicad" / "lib_build"


def run(d, build=True):
    if build:
        subprocess.run(["python3", "build_lib.py"], cwd=d, capture_output=True, check=True)
    r = subprocess.run(["python3", "check_lib.py"], cwd=d, capture_output=True, text=True)
    return r.returncode, [l for l in r.stdout.splitlines() if l.startswith("ERROR")][:2]


def sub(path, a, b):
    s = path.read_text()
    assert a in s, a
    path.write_text(s.replace(a, b, 1))


mutations = {
    "RGF pads back to ±2.1": lambda d: sub(d / "build_lib.py", "pad(1 + i, -2.4,", "pad(1 + i, -2.1,"),
    "swap 1N4148W/B5819W LCSC": lambda d: (sub(d / "parts.py", 'dict(lcsc="C81598"', 'dict(lcsc="C8598X"'),),
    "swap 1N4148W/B5819W mapping": lambda d: (sub(d / "parts.py", '"1N4148W": "1N4148W", "MMSZ5242B 12V": "MMSZ5242B", "B5819W": "B5819W"',
                                                  '"1N4148W": "B5819W", "MMSZ5242B 12V": "MMSZ5242B", "B5819W": "1N4148W"')),
    "diode K/A swapped (SMBJ20A)": lambda d: sub(d / "parts.py", 'fp="Diode_SMD:D_SMB"),', 'fp="Diode_SMD:D_SMB", rename={"1": "A", "2": "K"}),'),
    "C1 polarity swapped": lambda d: sub(d / "parts.py", 'rename={"1": "+", "2": "-"}', 'rename={"1": "-", "2": "+"}'),
    "DRV8316 pin 22 renumbered": lambda d: sub(d / "parts.py", '("22", "nFAULT", "open_collector", "R")', '("24", "nFAULT", "open_collector", "R")'),
    "extra copper pad reusing '5'": lambda d: sub(d / "build_lib.py", "pads.append(pad(41, 0, 0,", "pads.append(pad(5, 0, 3.0, 0.2, 0.2)); pads.append(pad(41, 0, 0,"),
    "EP without copper": lambda d: sub(d / "build_lib.py", 'pads.append(pad(41, 0, 0, 3.7, 5.7, shape="rect", layers=\'"F.Cu" "F.Mask"\'))',
                                           'pads.append(pad(41, 0, 0, 3.7, 5.7, shape="rect", layers=\'"F.Mask"\'))'),
    "courtyard too small": lambda d: sub(d / "build_lib.py", "(-2.95, -3.95, 2.95, 3.95)", "(-2.5, -3.5, 2.5, 3.5)"),
    "74LVC08 unit pin names wrong": lambda d: sub(d / "parts.py", '"1": "1A", "2": "1B", "3": "1Y"', '"1": "1B", "2": "1A", "3": "1Y"'),
    "connected pin typed no_connect (DRV8316 nFAULT)": lambda d: sub(d / "parts.py", '("22", "nFAULT", "open_collector", "R")', '("22", "nFAULT", "no_connect", "R")'),
    "two outputs on one net (DRV8323 INLA typed output vs U6 1Y)": lambda d: sub(d / "parts.py", '("38", "INLA", "input", "L")', '("38", "INLA", "output", "L")'),
}
ok = True
for name, fn in mutations.items():
    d = fresh()
    fn(d)
    rc, errs = run(d)
    status = "caught" if rc == 1 else "MISSED"
    ok &= rc == 1
    print(f"{status:7s} {name}: {errs[0] if errs else ''}"[:170])
d = fresh()
rc, _ = run(d)
print("baseline exit", rc)
shutil.rmtree(WORK.parent)
print("ALL CAUGHT" if ok and rc == 0 else "PROBLEM")
sys.exit(0 if ok and rc == 0 else 1)
