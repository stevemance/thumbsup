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
    shutil.copy(SRC / "BOM.md", WORK / "BOM.md")
    shutil.copytree(SRC / "kicad" / "lib_build", WORK / "kicad" / "lib_build")
    return WORK / "kicad" / "lib_build"


def run(d, build=True):
    if build:
        subprocess.run(["python3", "build_lib.py"], cwd=d, capture_output=True, check=True)
    r = subprocess.run(["python3", "check_lib.py"], cwd=d, capture_output=True, text=True)
    errs = [l for l in r.stdout.splitlines() if l.startswith("ERROR")][:2]
    if r.returncode and not errs:  # a crash is not a detection
        return 2, [r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "crashed"]
    return r.returncode, errs


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
    # round-2 tooling review mutations
    "J1 odd/even columns swapped": lambda d: (sub(d / "build_lib.py", "pads.append(pad(2 * i + 1, -x, y, pw, ph))", "pads.append(pad(2 * i + 1, x, y, pw, ph))"),
                                              sub(d / "build_lib.py", "pads.append(pad(2 * i + 2, x, y, pw, ph))", "pads.append(pad(2 * i + 2, -x, y, pw, ph))")),
    "J1 pitch 1.0 instead of 1.27": lambda d: sub(d / "parts.py", "n=10, pitch=1.27, pad=(2.5, 0.74), x=2.0", "n=10, pitch=1.0, pad=(2.5, 0.74), x=2.0"),
    "HoLR land moved outward": lambda d: sub(d / "parts.py", "pad=(3.1, 4.0), x=2.2, body=(6.4, 3.2)", "pad=(3.1, 4.0), x=2.5, body=(6.4, 3.2)"),
    "JIERR given the HoLR land": lambda d: sub(d / "parts.py", "pad=(2.1, 4.0), x=3.1, body=(6.35, 3.2)", "pad=(3.1, 4.0), x=2.2, body=(6.35, 3.2)"),
    "RGF signal pads without paste": lambda d: sub(d / "build_lib.py", "pads.append(pad(1 + i, -2.4, -2.75 + 0.5 * i, pw, ph))",
                                                   "pads.append(pad(1 + i, -2.4, -2.75 + 0.5 * i, pw, ph, layers='\"F.Cu\" \"F.Mask\"'))"),
    "EP paste windows deleted": lambda d: sub(d / "build_lib.py", """            pads.append(pad("", cx, cy, 1.05, 1.15, rr=0.1, layers='"F.Paste"'))""", "            pass"),
    "paste window over signal pads": lambda d: sub(d / "build_lib.py", "for cx in (-1.25, 0, 1.25):", "for cx in (-1.25, 0, 2.2):"),
    "74LVC08 gate grouping wrong": lambda d: sub(d / "parts.py", '[{"1", "2", "3"}, {"4", "5", "6"},', '[{"1", "2", "6"}, {"4", "5", "3"},'),
    "B5819W symbol carries the 1N4148W part (mapping + LCSC swapped)": lambda d: (
        sub(d / "parts.py", '"1N4148W": "1N4148W", "MMSZ5242B 12V": "MMSZ5242B", "B5819W": "B5819W"',
            '"1N4148W": "B5819W", "MMSZ5242B 12V": "MMSZ5242B", "B5819W": "1N4148W"'),
        sub(d / "parts.py", 'dict(lcsc="C81598"', 'dict(lcsc="TMPX"'), sub(d / "parts.py", 'dict(lcsc="C8598"', 'dict(lcsc="C81598"'),
        sub(d / "parts.py", 'dict(lcsc="TMPX"', 'dict(lcsc="C8598"')),
}


def hide_first_vm(d):  # post-build: hide DRV8316 VM pin 9 (a hidden power_in becomes a global net)
    f = d / "out" / "motor_board.kicad_sym"
    s = f.read_text()
    i = s.index('(symbol "DRV8316CRRGFR_1_1"')
    j = s.index('(name "VM"', i)
    f.write_text(s[:j] + "(hide yes)\n" + s[j:])


def pad_to_back(d):  # post-build: move an SH connector signal pad to the back side
    f = d / "out" / "motor_board.pretty" / "SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB.kicad_mod"
    s = f.read_text()
    f.write_text(s.replace('(layers "F.Cu" "F.Paste" "F.Mask")', '(layers "B.Cu" "B.Paste" "B.Mask")', 1))


post_mutations = {"hidden power_in pin (DRV8316 VM)": hide_first_vm, "pad moved to the back side": pad_to_back}
ok = True
for name, fn in list(mutations.items()) + [(k, v) for k, v in post_mutations.items()]:
    d = fresh()
    if name in post_mutations:
        subprocess.run(["python3", "build_lib.py"], cwd=d, capture_output=True, check=True)
        fn(d)
        rc, errs = run(d, build=False)
    else:
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
