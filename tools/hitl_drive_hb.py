#!/usr/bin/env python3
"""HITL suite for the DRV8874 H-bridge drive (firmware/src/drive_hbridge.c).

Each test demonstrates one capability against independent ground truth:
the ADALM2000 (H-bridge input pins, SLEEP, latency markers, voltage across each
motor) and the bench PSU (supply voltage and current).  The robot runs
thumbsup_hitl.uf2 and the emulator Pico supplies a real Bluetooth controller.

  ./tools/hitl_drive_hb.py --list
  ./tools/hitl_drive_hb.py all
  ./tools/hitl_drive_hb.py direction speed_estimate

Artifacts (captures, logs, results.json) go to hitl_logs/drive_hb_<stamp>/.
The wheels must be free to spin; nothing here loads them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hitl_orchestrator as ho  # noqa: E402
from common import HITL_STATUS_RE, parse_kv_payload  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PSU_CH = 1
PSU_V = 12.0
PSU_I = 3.0
DRV_RE_PREFIX = "HITL DRV "


class TestFailure(Exception):
    pass


def check(cond: bool, msg: str, results: dict) -> None:
    results.setdefault("checks", []).append({"ok": bool(cond), "msg": msg})
    print(("  PASS " if cond else "  FAIL ") + msg, flush=True)


class M2K:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.n_caps = 0
        self.p = subprocess.Popen([str(REPO / "tools" / "m2k_hb_worker.py")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
        self._expect("READY", 30)

    def _expect(self, word: str, timeout: float) -> str:
        # The worker only ever replies with one line per step; blocking read.
        line = self.p.stdout.readline().strip()
        if not line.startswith(word):
            raise RuntimeError(f"M2K worker: expected {word}, got {line!r}")
        return line[len(word):].strip()

    def start(self, seconds: float, rate: int = 1_000_000, name: str | None = None) -> str:
        """Starts a capture; returns its path.  Call finish() after the stimulus."""
        self.n_caps += 1
        path = str(self.out_dir / f"{self.n_caps:03d}_{name or 'cap'}.npz")
        self.p.stdin.write(f"CAP {rate} {int(seconds * rate)} {path}\n")
        self.p.stdin.flush()
        self._expect("ARMED", 10)
        return path

    def finish(self) -> dict:
        return json.loads(self._expect("DONE", 60))

    def analyse(self, path: str, **args) -> dict:
        self.p.stdin.write(f"AN {path} {json.dumps(args)}\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline().strip()
        if not line.startswith("RESULT"):
            raise RuntimeError(f"M2K analysis failed: {line}")
        return json.loads(line[len("RESULT"):])

    def close(self) -> None:
        try:
            self.p.stdin.write("QUIT\n")
            self.p.stdin.flush()
            self.p.wait(5)
        except Exception:
            self.p.kill()


class Rig:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.robot = ho.SerialLogger(serial.Serial(ho.resolve_robot_port(), 115200, timeout=0.05),
                                     out_dir / "robot.log", "robot")
        self.gp = ho.SerialLogger(serial.Serial(ho.resolve_gamepad_port(), 115200, timeout=0.05),
                                  out_dir / "gamepad.log", "gamepad")
        self.m2k = M2K(out_dir)
        self.last_status: dict[str, str] = {}
        self.m2k_cal: dict = {}
        self._rx_buf = b""
        self.health_events: list[str] = []

    def close(self) -> None:
        for fn in (self.neutral, lambda: self.cmd("HITL DRVSET L OFF"), lambda: self.cmd("HITL DRVSET R OFF")):
            try:
                fn()
            except Exception:
                pass
        self.m2k.close()
        self.robot.close()
        self.gp.close()

    # -- robot console ----------------------------------------------------
    def _robot_line(self) -> str | None:
        """Complete lines only (readline() with a timeout can return half a
        long line)."""
        ser = self.robot._ser
        n = ser.in_waiting
        if n:
            self._rx_buf += ser.read(n)
        if b"\n" not in self._rx_buf:
            return None
        raw, self._rx_buf = self._rx_buf.split(b"\n", 1)
        text = raw.decode("utf-8", errors="replace").rstrip()
        if text:
            self.robot.write_rx(text)
            if text.startswith("DRV HEALTH motor"):
                self.health_events.append(text)
        return text

    def pump(self, seconds: float = 0.0, until=None) -> str | None:
        """Reads robot/emulator lines for `seconds`, or until until(line) is true."""
        end = time.monotonic() + seconds
        while True:
            self.gp.read_line()
            line = self._robot_line()
            if line:
                m = HITL_STATUS_RE.match(line)
                if m:
                    self.last_status = parse_kv_payload(m.group(1))
                if until and until(line):
                    return line
                continue
            if time.monotonic() >= end:
                return None
            time.sleep(0.002)

    def cmd(self, line: str, reply_prefix: str | None = None, timeout: float = 2.0) -> str:
        self.robot.send_line(line)
        prefix = reply_prefix or " ".join(line.split()[:2])
        got = self.pump(timeout, until=lambda l: l.startswith(prefix) or l.startswith("ERR"))
        if got is None or got.startswith("ERR"):
            raise TestFailure(f"no reply to {line!r}: {got}")
        return got

    def drv(self) -> dict:
        line = self.cmd("HITL DRV", DRV_RE_PREFIX)
        return {k: (int(v) if v.lstrip("-").isdigit() else v) for k, v in
                (kv.split("=", 1) for kv in line[len(DRV_RE_PREFIX):].split() if "=" in kv)}

    def status(self, timeout: float = 1.0) -> dict:
        self.last_status = {}
        self.pump(timeout, until=lambda l: l.startswith("HITL STATUS"))
        return self.last_status

    # -- controller ---------------------------------------------------------
    def connect(self) -> None:
        # ensure_robot_ready reads the port itself; hand it a clean buffer.
        self._rx_buf = b""
        self.health_events: list[str] = []
        # Right after a flash/reset the robot needs a few seconds before its
        # console and Bluetooth answer.
        deadline = time.monotonic() + 20.0
        while True:
            self.robot.send_line("HITL BTADDR")
            if self.pump(1.0, until=lambda l: l.startswith("HITL BTADDR")):
                break
            if time.monotonic() > deadline:
                raise TestFailure("robot console not answering")
        ho.ensure_robot_ready(self.robot, self.gp, timeout_s=15.0)

    def disconnect(self) -> None:
        self.gp.send_line("DISCONNECT")

    def neutral(self) -> None:
        for c in ho.GAMEPAD_NEUTRAL_CMDS:
            self.gp.send_line(c)

    def stick(self, ly: int | None = None, rx: int | None = None) -> None:
        """Split layout: LY throttle, RX turn.  Emulator axis units -127..127."""
        if ly is not None:
            self.gp.send_line(f"AXIS LY {ly}")
        if rx is not None:
            self.gp.send_line(f"AXIS RX {rx}")

    # -- ground truth ----------------------------------------------------------
    def calibrate_m2k(self, duty: int = 300) -> dict:
        """Per-channel gain and offset of the M2K motor-voltage inputs.

        Each motor is driven forward then reverse at `duty`; the PWM rail
        levels are then +V and -V across the motor (minus small FET drops),
        with the same common mode, so gain = (high_fwd - low_rev) / 2V and
        offset = (high_fwd + low_rev) / 2.  The supply V comes from the PSU."""
        cal = {}
        for side, ch in (("L", 0), ("R", 1)):
            levels = {}
            for sign in (1, -1):
                self.cmd(f"HITL DRVSET {side} {sign * duty}")
                time.sleep(0.6)
                p = self.m2k.start(0.02, name=f"cal_{side}{sign:+d}")
                self.m2k.finish()
                levels[sign] = self.m2k.analyse(p, kind="levels")[ch]
                self.cmd(f"HITL DRVSET {side} 0")
                time.sleep(0.8)
            self.cmd(f"HITL DRVSET {side} OFF")
            vb = self.psu_measure()[0]
            hi, lo = levels[1]["high"], levels[-1]["low"]
            cal[side] = {"gain": (hi - lo) / (2 * vb), "offset": (hi + lo) / 2, "vb": vb}
        self.m2k_cal = cal
        return cal

    def probe(self, side: str, window_ms: int = 8) -> dict:
        """Coasts one motor briefly; returns the firmware's estimate taken just
        before and the back-EMF measured across the motor (volts, motor frame)."""
        ch = 0 if side == "L" else 1
        p = self.m2k.start(0.06, name=f"probe_{side}")
        time.sleep(0.015)
        line = self.cmd(f"HITL DRVPROBE {side} {window_ms}", "DRV PROBE")
        self.m2k.finish()
        kv = dict(t.split("=", 1) for t in line.split()[2:])
        wins = self.m2k.analyse(p, kind="coast", min_ms=window_ms * 0.6, vb=self.m2k_cal[side]["vb"])[side]
        cal = self.m2k_cal[side]
        truth = None
        if len(wins) == 1:
            truth = (wins[0]["emf0_v"] - cal["offset"]) / cal["gain"]
        return {"side": side, "est_v": int(kv["emf_mv"]) / 1000.0, "truth_v": truth,
                "duty": int(kv["duty"]), "current_ma": int(kv["current_ma"]), "capture": p,
                "windows": wins}

    # -- PSU -----------------------------------------------------------------
    @staticmethod
    def _retry(fn, tries: int = 4):
        # The DP832's USBTMC link occasionally times out a read; retry.
        for k in range(tries):
            try:
                return fn()
            except Exception:
                if k == tries - 1:
                    raise
                time.sleep(0.3)

    @staticmethod
    def psu_set(v: float, i: float = PSU_I) -> None:
        Rig._retry(lambda: ho.labctl_psu_set(PSU_CH, v, i))

    @staticmethod
    def psu_measure() -> tuple[float, float]:
        snap = Rig._retry(lambda: ho.labctl_psu_snapshot(PSU_CH))["values"][str(PSU_CH)]
        return float(snap["voltage"]), float(snap["current"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
TESTS: dict[str, tuple] = {}


def test(name: str, doc: str):
    def deco(fn):
        TESTS[name] = (fn, doc)
        return fn
    return deco


def baseline(rig: Rig) -> None:
    """Known state between tests: connected, neutral, defaults, wheels stopped."""
    rig.neutral()
    if Rig.psu_measure()[0] < PSU_V - 0.2:
        Rig.psu_set(PSU_V)
        time.sleep(0.5)
    if rig.drv().get("awake") != 1:
        rig.connect()
    # (other suites leave a battery override in place; the arm check honours it)
    for c in ("HITL BATTERY OFF", "HITL DRVSET L OFF", "HITL DRVSET R OFF", "HITL DRVACCEL 0", "HITL DRVDRAG 1000",
              "HITL DRVMATCH 1", "HITL DRVDERATE L 1000", "HITL DRVDERATE R 1000"):
        rig.cmd(c)
    rig.pump(0.8)


def drive_spin(rig: Rig, side: str, duty: int, settle: float = 1.0) -> None:
    """Runs a motor at `duty`, stopping first if that would reverse it."""
    cur = rig.drv()[side.lower() + "_app"]
    if cur and duty and (cur > 0) != (duty > 0):
        rig.cmd(f"HITL DRVSET {side} 0")
        rig.pump(1.0)
    rig.cmd(f"HITL DRVSET {side} {duty}")
    rig.pump(settle)


def first_change(trace: list[float], start_idx: int, threshold: float) -> int | None:
    for k in range(start_idx, len(trace)):
        if abs(trace[k]) >= threshold:
            return k
    return None


@test("direction", "each motor both ways: IN pins at 20 kHz, motor voltage = duty x supply")
def t_direction(rig: Rig, res: dict) -> None:
    baseline(rig)
    vb = Rig.psu_measure()[0]
    res["runs"] = []
    for side in ("L", "R"):
        for duty in (300, 700, -300, -700):
            drive_spin(rig, side, duty, 0.8)
            p = rig.m2k.start(0.02, name=f"dir_{side}{duty}")
            rig.m2k.finish()
            ph = rig.m2k.analyse(p, kind="summary")
            lv = rig.m2k.analyse(p, kind="drive", bin_us=20000)[side]
            in1, in2 = ("2", "3") if side == "L" else ("5", "6")
            freq = max(ph["dio"][in1]["freq_hz"], ph["dio"][in2]["freq_hz"])
            drive = lv["drive"][0]
            cal = rig.m2k_cal[side]
            ch = 0 if side == "L" else 1
            v_motor = (ph["analog"][ch]["mean"] - cal["offset"]) / cal["gain"]
            run = {"side": side, "duty": duty, "pwm_hz": freq, "in_drive_frac": drive, "v_motor": round(v_motor, 3),
                   "v_expected": round(duty / 1000 * vb, 3)}
            res["runs"].append(run)
            check(abs(freq - 20000) < 200, f"{side} {duty:+d}: PWM {freq:.0f} Hz (20 kHz)", res)
            check(abs(drive - duty / 1000) < 0.01, f"{side} {duty:+d}: drive fraction on the pins {drive:+.3f}", res)
            # Dead time and FET drops take a little off the average.
            check((v_motor > 0) == (duty > 0) and abs(v_motor - duty / 1000 * vb) < 0.08 * abs(duty / 1000 * vb) + 0.15,
                  f"{side} {duty:+d}: motor voltage {v_motor:+.2f} V vs {duty / 1000 * vb:+.2f} V", res)
        rig.cmd(f"HITL DRVSET {side} 0")
        rig.pump(1.0)
        rig.cmd(f"HITL DRVSET {side} OFF")


@test("stick_mapping", "controller sticks -> both wheels: forward, back, spin turns (split layout)")
def t_stick_mapping(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.cmd("HITL DRVMATCH 0")
    cases = [("forward", 127, 0), ("back", -127, 0), ("spin right", 0, 127), ("spin left", 0, -127),
             ("half forward", 64, 0)]
    res["cases"] = []
    prev = None
    for name, ly, rx in cases:
        rig.stick(ly=0, rx=0)
        rig.pump(1.0)
        rig.stick(ly=ly, rx=rx)
        rig.pump(0.6)
        d = rig.drv()
        res["cases"].append({"name": name, "ly": ly, "rx": rx, "l": d["l_app"], "r": d["r_app"]})
        print(f"    {name}: left {d['l_app']} right {d['r_app']}", flush=True)
    rig.stick(ly=0, rx=0)
    c = {x["name"]: x for x in res["cases"]}
    f, b = c["forward"], c["back"]
    # Motors face each other: robot forward is left + / right - in motor frame.
    check(f["l"] > 500 and f["r"] < -500 and abs(f["l"] + f["r"]) < 30, f"forward drives both wheels forward ({f['l']}/{f['r']})", res)
    check(b["l"] == -f["l"] and b["r"] == -f["r"], f"back mirrors forward ({b['l']}/{b['r']})", res)
    sr, sl = c["spin right"], c["spin left"]
    check(sr["l"] * sr["r"] > 0 and sl["l"] == -sr["l"] and sl["r"] == -sr["r"],
          f"spin turns run the wheels the same motor direction, mirrored ({sr['l']}/{sr['r']}, {sl['l']}/{sl['r']})", res)
    h = c["half forward"]
    check(0 < h["l"] < f["l"], f"half stick gives less duty ({h['l']} < {f['l']})", res)
    rig.pump(0.8)


@test("latency", "stick step -> H-bridge pins: robot receive marker to output, and end to end")
def t_latency(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.cmd("HITL DRVMATCH 0")
    rx_to_out, e2e = [], []
    for k in range(12):
        rig.stick(ly=0)
        rig.pump(0.7)
        p = rig.m2k.start(0.25, name=f"lat{k}")
        time.sleep(0.05 + 0.007 * k)       # spread the step over the BT poll phase
        rig.stick(ly=127)
        rig.m2k.finish()
        dr = rig.m2k.analyse(p, kind="drive", bin_us=50)
        mk = dr["markers"]
        rx = [t for t in mk["1"]["rise_s"] if t > 0.01]
        tx = [t for t in mk["0"]["rise_s"] if t > 0.01]
        bin_s = dr["bin_s"]
        i_out = first_change(dr["L"]["drive"], int(0.01 / bin_s), 0.2)
        if not rx or i_out is None:
            continue
        t_out = i_out * bin_s
        rx_to_out.append((t_out - rx[0]) * 1000)
        if tx:
            e2e.append((t_out - tx[0]) * 1000)
    rig.stick(ly=0)
    res["rx_to_out_ms"] = [round(x, 3) for x in rx_to_out]
    res["emu_to_out_ms"] = [round(x, 3) for x in e2e]
    check(len(rx_to_out) >= 10, f"{len(rx_to_out)}/12 steps measured", res)
    if rx_to_out:
        rs = sorted(rx_to_out)
        print(f"    robot rx -> pins: median {statistics.median(rs):.2f} ms, max {rs[-1]:.2f} ms", flush=True)
        check(rs[-1] < 2.0, f"robot report -> H-bridge output max {rs[-1]:.2f} ms (< 2 ms; was a 10 ms servo frame + ESC filter)", res)
    if e2e:
        es = sorted(e2e)
        res["emu_to_out_median_ms"] = statistics.median(es)
        print(f"    emulator send -> pins: median {statistics.median(es):.2f} ms, max {es[-1]:.2f} ms", flush=True)
        # Informational: needs the emulator marker on DIO0 (see docs).
    rig.pump(0.8)


@test("brake_vs_coast", "zero stick brakes (drag brake 100%) vs coasts (0%): wheel speed 150 ms after release")
def t_brake(rig: Rig, res: dict) -> None:
    """Speed after release from the motor voltage: braking shorts the motor,
    so it is sampled with a coast probe 150 ms after release; coasting shows it
    directly, and a tiny drive command 150 ms after release closes the coast
    window so its end is the reading."""
    baseline(rig)
    out = {}
    cal = rig.m2k_cal["L"]
    for drag in (1000, 0):
        rig.cmd(f"HITL DRVDRAG {drag}")
        drive_spin(rig, "L", 700, 1.2)
        before = rig.probe("L")["truth_v"]
        rig.pump(0.3)
        p = rig.m2k.start(0.35, name=f"release_drag{drag}")
        time.sleep(0.02)
        t0 = time.monotonic()
        rig.robot.send_line("HITL DRVSET L 0")
        time.sleep(max(0.0, 0.15 - (time.monotonic() - t0)))
        if drag:
            rig.robot.send_line("HITL DRVPROBE L 8")
        else:
            rig.robot.send_line("HITL DRVSET L 30")
        rig.m2k.finish()
        wins = rig.m2k.analyse(p, kind="coast", min_ms=4, vb=cal["vb"])["L"]
        after = None
        if wins:
            w = wins[-1]
            raw = w["emf0_v"] if drag else w["emf_end_v"]
            after = (raw - cal["offset"]) / cal["gain"]
            out[drag] = {"before_v": before, "after_v": after, "window_ms": w["len_ms"]}
        rig.cmd("HITL DRVSET L 0")
        rig.pump(1.5)
    res["data"] = out
    rb = abs(out[1000]["after_v"] / out[1000]["before_v"]) if 1000 in out else None
    rc = abs(out[0]["after_v"] / out[0]["before_v"]) if 0 in out else None
    print(f"    speed left ~150 ms after release: brake {rb}, coast {rc}", flush=True)
    check(rb is not None and rb < 0.10, f"brake: wheel at {rb if rb is None else round(rb * 100)}% of its speed (< 10%)", res)
    check(rc is not None and rc > 3 * max(rb or 0, 0.05),
          f"coast: wheel still at {rc if rc is None else round(rc * 100)}% (well above brake)", res)
    rig.cmd("HITL DRVDRAG 1000")
    rig.cmd("HITL DRVSET L OFF")


@test("sleep", "drivers asleep (SLEEP low, outputs off) without a controller; awake once it is ready")
def t_sleep(rig: Rig, res: dict) -> None:
    baseline(rig)
    p = rig.m2k.start(1.5, name="disconnect")
    time.sleep(0.2)
    t0 = time.monotonic()
    rig.disconnect()
    rig.m2k.finish()
    dr = rig.m2k.analyse(p, kind="drive", bin_us=1000)
    falls = dr["markers"]["7"]["fall_s"]
    check(len(falls) == 1, f"SLEEP pin fell once on disconnect ({falls})", res)
    rig.pump(1.0)
    d = rig.drv()
    check(d["awake"] == 0, "driver reports asleep while disconnected", res)
    p = rig.m2k.start(0.05, name="asleep")
    rig.m2k.finish()
    sm = rig.m2k.analyse(p, kind="summary")["dio"]
    check(sm["7"]["duty"] == 0.0, "SLEEP held low while disconnected", res)
    # Commands while asleep must not drive anything.
    rig.robot.send_line("HITL DRVSET L 500")
    rig.pump(0.3)
    p = rig.m2k.start(0.05, name="asleep_cmd")
    rig.m2k.finish()
    sm = rig.m2k.analyse(p, kind="summary")["dio"]
    check(sm["7"]["duty"] == 0.0, "still asleep after a drive command with no controller", res)
    rig.robot.send_line("HITL DRVSET L OFF")
    rig.connect()
    p = rig.m2k.start(0.05, name="reconnected")
    rig.m2k.finish()
    sm = rig.m2k.analyse(p, kind="summary")["dio"]
    check(sm["7"]["duty"] == 1.0, "SLEEP high again once the controller is ready", res)
    check(rig.drv()["awake"] == 1, "driver reports awake with the controller ready", res)


@test("fault", "nFAULT: supply undervoltage (PSU to 3.8 V) is reported, drive recovers after")
def t_fault(rig: Rig, res: dict) -> None:
    baseline(rig)
    before = rig.drv()["fault_events"]
    Rig.psu_set(3.8)
    got = rig.pump(4.0, until=lambda l: l.startswith("DRV FAULT asserted"))
    d = rig.drv()
    check(got is not None and d["fault_events"] > before, f"fault reported at 3.8 V ({got})", res)
    check(d["fault"] == 1, "fault flag set while undervoltage", res)
    Rig.psu_set(PSU_V)
    got = rig.pump(4.0, until=lambda l: l.startswith("DRV FAULT cleared"))
    check(got is not None, "fault cleared when the supply returned", res)
    rig.pump(1.0)
    if rig.drv()["awake"] != 1:
        rig.connect()
    drive_spin(rig, "L", 400, 1.0)
    d = rig.drv()
    check(d["l_emf_mv"] > 2000 and d["fault"] == 0, f"motor runs again after the fault (emf {d['l_emf_mv']} mV)", res)
    rig.cmd("HITL DRVSET L 0")
    rig.pump(1.0)
    rig.cmd("HITL DRVSET L OFF")


@test("current_sense", "current sense vs PSU supply current (supply = quiescent + duty x motor current)")
def t_current(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.pump(1.0)
    _, i_idle = Rig.psu_measure()
    res["i_idle_a"] = i_idle
    res["points"] = []
    for side in ("L", "R"):
        for duty in (300, 600, 1000):
            drive_spin(rig, side, duty, 1.2)
            samples = []
            psu = []
            for _ in range(10):
                samples.append(rig.drv()[side.lower() + "_ma"])
                psu.append(Rig.psu_measure()[1])
            i_cs = statistics.mean(samples) / 1000
            i_psu = statistics.mean(psu)
            expect = i_idle + duty / 1000 * i_cs
            res["points"].append({"side": side, "duty": duty, "cs_a": round(i_cs, 4), "psu_a": i_psu,
                                  "psu_expected_a": round(expect, 4), "cs_ma_samples": samples,
                                  "psu_a_samples": psu})
            print(f"    {side} {duty}: CS spread {min(samples)}-{max(samples)} mA, PSU {min(psu) * 1000:.0f}-{max(psu) * 1000:.0f} mA", flush=True)
            check(abs(i_psu - expect) < 0.03 + 0.12 * duty / 1000 * i_cs,
                  f"{side} {duty}: CS {i_cs * 1000:.0f} mA -> supply {expect * 1000:.0f} mA predicted, {i_psu * 1000:.0f} mA measured", res)
        rig.cmd(f"HITL DRVSET {side} 0")
        rig.pump(1.0)
        rig.cmd(f"HITL DRVSET {side} OFF")


@test("speed_estimate", "steady wheel speed (back-EMF) estimate vs coast-probe ground truth, both motors and ways")
def t_speed(rig: Rig, res: dict) -> None:
    baseline(rig)
    res["points"] = []
    for side in ("L", "R"):
        for duty in (150, 300, 500, 700, 1000, -300, -700, -1000):
            drive_spin(rig, side, duty, 1.0)
            # Three probes: a damaged gearbox's load changes from one
            # millisecond to the next, so single readings scatter.
            probes = []
            for _ in range(3):
                pr = rig.probe(side)
                pr.pop("windows", None)
                probes.append(pr)
                rig.pump(0.25)
            ok = [p for p in probes if p["truth_v"] is not None]
            est = statistics.mean(p["est_v"] for p in ok) if ok else None
            truth = statistics.mean(p["truth_v"] for p in ok) if ok else None
            res["points"].append({"side": side, "duty": duty, "est_v": est, "truth_v": truth, "probes": probes})
            check(len(ok) >= 2 and abs(est - truth) < 0.6,
                  f"{side} {duty:+5d}: estimate {est if est is None else round(est, 2)} V, truth "
                  f"{truth if truth is None else round(truth, 2)} V (mean of {len(ok)})", res)
        rig.cmd(f"HITL DRVSET {side} 0")
        rig.pump(1.0)
        rig.cmd(f"HITL DRVSET {side} OFF")


@test("speed_dynamic", "speed estimate while accelerating from rest: probes 40/80/160/320 ms after a full step (3 starts each)")
def t_speed_dyn(rig: Rig, res: dict) -> None:
    """Start-up current swings +-30% with rotor position (commutator) and a
    worn gearbox adds load spikes, so each delay is measured on three starts
    and the means are compared (as speed_estimate does)."""
    baseline(rig)
    res["points"] = []
    cal = rig.m2k_cal["L"]
    for delay in (0.04, 0.08, 0.16, 0.32):
        runs = []
        for k in range(3):
            rig.cmd("HITL DRVSET L 0")
            rig.pump(1.5)
            p = rig.m2k.start(0.6, name=f"dyn{int(delay * 1000)}_{k}")
            time.sleep(0.02)
            rig.cmd("HITL DRVSET L 1000")
            time.sleep(delay)
            line = rig.cmd("HITL DRVPROBE L 6", "DRV PROBE")
            rig.m2k.finish()
            est = int(line.split("emf_mv=")[1].split()[0]) / 1000
            wins = rig.m2k.analyse(p, kind="coast", min_ms=3.5, vb=cal["vb"])["L"]
            if wins:
                runs.append({"est_v": est, "truth_v": (wins[-1]["emf0_v"] - cal["offset"]) / cal["gain"]})
        est = statistics.mean(r["est_v"] for r in runs) if runs else None
        truth = statistics.mean(r["truth_v"] for r in runs) if runs else None
        res["points"].append({"delay_s": delay, "est_v": est, "truth_v": truth, "runs": runs})
        check(len(runs) >= 2 and abs(est - truth) < 0.8,
              f"{int(delay * 1000)} ms after step (host-timed): estimate {est if est is None else round(est, 2)} V, "
              f"truth {truth if truth is None else round(truth, 2)} V (mean of {len(runs)})", res)
    rig.cmd("HITL DRVSET L 0")
    rig.pump(1.0)
    rig.cmd("HITL DRVSET L OFF")
    truths = [p["truth_v"] or 0 for p in res["points"]]
    check(truths[1] - truths[0] > 0.3 and all(b > a - 0.3 for a, b in zip(truths, truths[1:])),
          f"the wheel was still accelerating at the first probes ({[round(t, 2) for t in truths]})", res)


@test("resistance_cal", "winding resistance measured on starts from rest and drive->brake transitions: consistent and plausible")
def t_rcal(rig: Rig, res: dict) -> None:
    baseline(rig)
    for side in ("L", "R"):
        vals = []
        d0 = rig.drv()
        n0, b0 = d0[side.lower() + "_rcal_n"], d0[side.lower() + "_rrun_n"]
        for k in range(6):
            rig.cmd(f"HITL DRVSET {side} 0")
            rig.pump(1.2)
            rig.cmd(f"HITL DRVSET {side} {500 if k % 2 == 0 else -500}")
            rig.pump(0.5)
            d = rig.drv()
            vals.append(d[side.lower() + "_r_mohm"] / 1000)
        d1 = rig.drv()
        n1, b1 = d1[side.lower() + "_rcal_n"], d1[side.lower() + "_rrun_n"]
        rig.cmd(f"HITL DRVSET {side} 0")
        rig.pump(1.0)
        rig.cmd(f"HITL DRVSET {side} OFF")
        res[side] = {"r_ohm_after_each_start": vals, "measurements": n1 - n0}
        print(f"    {side}: R after each cycle {vals}", flush=True)
        check(n1 - n0 >= 5, f"{side}: {n1 - n0}/6 starts from rest produced a measurement", res)
        check(b1 - b0 >= 4, f"{side}: {b1 - b0} drive->brake transitions produced a running measurement", res)
        check(all(2.0 < v < 20.0 for v in vals), f"{side}: R within 2-20 ohm", res)
        spread = (max(vals) - min(vals)) / statistics.mean(vals)
        check(spread < 0.2, f"{side}: R spread {spread * 100:.0f}% across starts (< 20%)", res)


@test("accel_limit", "acceleration limit ramps speed-ups only; slowing and stopping stay instant")
def t_accel(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.cmd("HITL DRVMATCH 0")
    out = {}
    for rate in (0, 200):
        rig.cmd(f"HITL DRVACCEL {rate}")
        rig.stick(ly=0)
        rig.pump(1.0)
        p = rig.m2k.start(0.9, name=f"accel{rate}")
        time.sleep(0.05)
        rig.stick(ly=127)
        time.sleep(0.55)
        rig.stick(ly=0)
        rig.m2k.finish()
        dr = rig.m2k.analyse(p, kind="drive", bin_us=1000)
        tr = dr["L"]["drive"]
        top = max(tr)
        i0 = first_change(tr, 0, 0.02)
        i_top = next((k for k in range(i0 or 0, len(tr)) if tr[k] >= 0.95 * top), None)
        # (1 ms bins read 0.72/0.74 for 0.73: M2K sampling beats with the PWM.)
        i_stop = next((k for k in range(i_top or 0, len(tr)) if tr[k] < 0.01), None)
        stop_ms = None
        if i_stop is not None:
            i_last_high = max(k for k in range(i_top, i_stop) if tr[k] >= 0.5 * top)
            stop_ms = i_stop - i_last_high - 1
        out[rate] = {"top": top, "rise_ms": None if i0 is None or i_top is None else i_top - i0, "stop_ms": stop_ms}
        rig.pump(0.8)
    res["data"] = out
    print(f"    {out}", flush=True)
    top = out[200]["top"]
    expect_ms = 0.95 * top * 100 / 200 * 1000
    check(out[0]["rise_ms"] is not None and out[0]["rise_ms"] <= 2, f"limit off: 95% of full duty in {out[0]['rise_ms']} ms", res)
    check(out[200]["rise_ms"] is not None and abs(out[200]["rise_ms"] - expect_ms) < 0.1 * expect_ms + 5,
          f"200%/s: ramp to 95% of {top:.2f} took {out[200]['rise_ms']} ms (expected {expect_ms:.0f} ms)", res)
    check(out[200]["stop_ms"] is not None and out[200]["stop_ms"] <= 2, f"200%/s: release to zero in {out[200]['stop_ms']} ms (not ramped)", res)
    rig.cmd("HITL DRVACCEL 0")


@test("battery", "battery divider accuracy, low/critical alerts with hysteresis, alert-only, arming refused when low")
def t_battery(rig: Rig, res: dict) -> None:
    baseline(rig)
    res["accuracy"] = []
    for v in (9.0, 10.5, 12.0, 13.5, 15.0):
        Rig.psu_set(v)
        rig.pump(0.8)
        vm = Rig.psu_measure()[0]
        mv = statistics.mean(rig.drv()["batt_mv"] for _ in range(3))
        res["accuracy"].append({"psu_v": vm, "adc_v": mv / 1000})
        check(abs(mv / 1000 - vm) < 0.015 * vm + 0.05, f"{vm:.2f} V reads {mv / 1000:.3f} V", res)
    Rig.psu_set(12.0)
    rig.pump(1.0)

    def level_after(v: float, want: str, timeout: float = 25.0) -> str | None:
        Rig.psu_set(v)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            st = rig.status()
            if st.get("batt_level") == want:
                return want
        return rig.last_status.get("batt_level")

    # Settle the filter at 12 V first (5 s time constant).
    check(level_after(12.0, "OK", 30) == "OK", "12.0 V: OK", res)
    check(level_after(10.0, "LOW") == "LOW", "10.0 V: LOW (below 10.2)", res)
    check(level_after(9.3, "CRITICAL") == "CRITICAL", "9.3 V: CRITICAL (below 9.6)", res)
    # Alert only: still drives.
    rig.stick(ly=127)
    rig.pump(0.6)
    d = rig.drv()
    rig.stick(ly=0)
    # (applied may be below target: speed matching trims the healthy side)
    check(d["l_tgt"] > 500 and d["l_app"] > 300 and d["awake"] == 1,
          f"drive still works while CRITICAL (left command {d['l_tgt']}, applied {d['l_app']})", res)
    # Arming refused at low battery.
    rig.pump(1.0)
    rig.gp.send_line("BTN B 1")
    rig.pump(0.15)
    rig.gp.send_line("BTN B 0")
    rig.pump(1.0)
    st = rig.status()
    check(st.get("armed") == "0", "weapon arm refused at 9.3 V", res)
    check(level_after(9.8, "LOW", 25) == "LOW" or rig.last_status.get("batt_level") == "CRITICAL",
          "9.8 V: hysteresis (CRITICAL until 9.9 V)", res)
    check(level_after(10.4, "LOW", 25) == "LOW", "10.4 V: LOW (hysteresis until 10.5 V)", res)
    check(level_after(12.0, "OK", 30) == "OK", "12.0 V: back to OK", res)
    st = rig.status()
    if st.get("armed") == "1":
        rig.gp.send_line("BTN B 1")
        rig.pump(0.15)
        rig.gp.send_line("BTN B 0")


@test("current_limit", "hard reversal at full speed hits the DRV8874 current limit: chopping reported on nFAULT, no lockout")
def t_ilimit(rig: Rig, res: dict) -> None:
    baseline(rig)
    drive_spin(rig, "L", 1000, 1.0)
    before = rig.drv()["fault_events"]
    p = rig.m2k.start(0.3, name="reversal")
    time.sleep(0.05)
    rig.cmd("HITL DRVSET L -1000")
    rig.m2k.finish()
    rig.pump(1.0)
    d = rig.drv()
    res["fault_events"] = d["fault_events"] - before
    check(d["fault_events"] > before, f"current-limit events reported ({d['fault_events'] - before})", res)
    check(d["l_emf_mv"] < -8000, f"motor reversed to full speed (emf {d['l_emf_mv']} mV)", res)
    rig.cmd("HITL DRVSET L 0")
    rig.pump(1.0)
    rig.cmd("HITL DRVSET L OFF")


def learn_straight(rig: Rig, levels=(64, 100, 127), dwell: float = 1.5) -> None:
    for sign in (1, -1):
        for ly in levels:
            rig.stick(ly=sign * ly)
            rig.pump(dwell)
        rig.stick(ly=0)
        rig.pump(1.0)


def straight_ratio(rig: Rig, ly: int) -> dict:
    rig.stick(ly=ly)
    rig.pump(1.0)
    d = rig.drv()
    pl = rig.probe("L")
    rig.pump(0.3)
    pr = rig.probe("R")
    rig.stick(ly=0)
    rig.pump(1.0)
    ratio = abs(pr["truth_v"] / pl["truth_v"]) if pl["truth_v"] and pr["truth_v"] else None
    return {"ly": ly, "l_app": d["l_app"], "r_app": d["r_app"], "l_scale": d["l_scale"], "r_scale": d["r_scale"],
            "l_truth_v": pl["truth_v"], "r_truth_v": pr["truth_v"], "ratio_r_over_l": ratio}


@test("health_detect", "learned wheel health flags the damaged right gearbox, not the left")
def t_health_detect(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.cmd("HITL DRVHEALTH RESET", "DRV HEALTH")
    rig.health_events.clear()
    rig.cmd("HITL DRVMATCH 0")
    learn_straight(rig)
    d = rig.drv()
    events = list(rig.health_events)
    res["events"] = events
    res["health"] = {"l": d["l_health"], "r": d["r_health"]}
    check(any("motor=R level=DEGRADED" in e for e in events), f"right reported DEGRADED ({events})", res)
    check(d["r_degraded"] == 1 and d["l_degraded"] == 0, f"health L {d['l_health']}, R {d['r_health']} (alert < 850)", res)
    check(not any("motor=L" in e for e in events), "no alert for the healthy left at any point", res)


@test("health_match", "speed matching keeps the wheels at the commanded ratio: real damaged gearbox at full stick")
def t_health_match(rig: Rig, res: dict) -> None:
    baseline(rig)
    rig.cmd("HITL DRVHEALTH RESET", "DRV HEALTH")
    rig.cmd("HITL DRVMATCH 0")
    learn_straight(rig)
    off = straight_ratio(rig, 127)
    rig.cmd("HITL DRVMATCH 1")
    learn_straight(rig, levels=(127,), dwell=2.0)     # let the trimmed duty be learned
    on = straight_ratio(rig, 127)
    res["off"], res["on"] = off, on
    print(f"    off {off}\n    on  {on}", flush=True)
    check(off["ratio_r_over_l"] is not None and on["ratio_r_over_l"] is not None, "ground truth measured", res)
    if off["ratio_r_over_l"] and on["ratio_r_over_l"]:
        eo, en = abs(1 - off["ratio_r_over_l"]), abs(1 - on["ratio_r_over_l"])
        check(en < 0.10 and en < eo / 2, f"wheel speed mismatch {eo * 100:.0f}% -> {en * 100:.0f}% (< 10%, at least halved)", res)
        check(on["l_scale"] < 1000 and on["r_scale"] == 1000, "only the healthy (faster) left wheel was slowed", res)


@test("health_simulated", "simulated 55% duty loss on the left: detected, right trimmed (down to the 60% floor), mismatch reduced")
def t_health_sim(rig: Rig, res: dict) -> None:
    """The rig's right gearbox is genuinely damaged, so the simulated loss on
    the left has to be large to make the left the weak side - large enough
    that full matching would need the right below DRIVE_MATCH_MIN_SCALE (60%).
    By design matching stops there (a dead motor must not cripple the good
    side), so this checks detection, the trim and the floor, and that the
    mismatch shrinks; full matching is shown by health_match."""
    baseline(rig)
    rig.cmd("HITL DRVDERATE L 450")
    rig.cmd("HITL DRVHEALTH RESET", "DRV HEALTH")
    rig.health_events.clear()
    rig.cmd("HITL DRVMATCH 0")
    learn_straight(rig)
    d = rig.drv()
    res["events"] = list(rig.health_events)
    check(any("motor=L level=DEGRADED" in e for e in rig.health_events) and d["l_degraded"] == 1,
          f"left reported DEGRADED (health {d['l_health']}, events {rig.health_events})", res)
    res["runs"] = []
    for ly in (100, -100):
        rig.cmd("HITL DRVMATCH 0")
        off = straight_ratio(rig, ly)
        rig.cmd("HITL DRVMATCH 1")
        rig.stick(ly=ly)
        rig.pump(3.0)          # the trimmed duty gets learned too
        rig.stick(ly=0)
        rig.pump(1.0)
        on = straight_ratio(rig, ly)
        res["runs"].append({"off": off, "on": on})
        print(f"    LY {ly}: off {off}\n            on  {on}", flush=True)
        if off["ratio_r_over_l"] and on["ratio_r_over_l"]:
            eo, en = abs(1 - off["ratio_r_over_l"]), abs(1 - on["ratio_r_over_l"])
            check(en < 0.8 * eo, f"LY {ly}: mismatch {eo * 100:.0f}% -> {en * 100:.0f}% (reduced)", res)
            check(600 <= on["r_scale"] < 1000 and on["l_scale"] == 1000,
                  f"LY {ly}: right trimmed to {on['r_scale'] / 10:.0f}% (floor 60%), left untouched", res)
        else:
            check(False, f"LY {ly}: ground truth missing", res)
    rig.cmd("HITL DRVDERATE L 1000")
    rig.cmd("HITL DRVHEALTH RESET", "DRV HEALTH")


def run(names: list[str], out_dir: Path) -> int:
    rig = Rig(out_dir)
    all_results = {}
    failed = 0
    try:
        Rig.psu_set(PSU_V)
        time.sleep(0.5)
        rig.connect()
        baseline(rig)
        all_results["m2k_calibration"] = rig.calibrate_m2k()
        print(f"M2K calibration: {all_results['m2k_calibration']}", flush=True)
        for name in names:
            fn, doc = TESTS[name]
            print(f"== {name}: {doc}", flush=True)
            res: dict = {"name": name, "doc": doc}
            try:
                fn(rig, res)
            except Exception as e:
                res.setdefault("checks", []).append({"ok": False, "msg": f"exception: {e!r}"})
                res["traceback"] = traceback.format_exc()
                print(f"  FAIL exception: {e!r}", flush=True)
            res["passed"] = all(c["ok"] for c in res.get("checks", [])) and bool(res.get("checks"))
            failed += not res["passed"]
            all_results[name] = res
            print(f"   -> {'PASS' if res['passed'] else 'FAIL'}", flush=True)
            (out_dir / "results.json").write_text(json.dumps(all_results, indent=1))
    finally:
        rig.close()
    print(f"\n{len(names) - failed}/{len(names)} tests passed; artifacts in {out_dir}")
    return 1 if failed else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tests", nargs="*", help="test names, or 'all'")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list or not args.tests:
        for name, (_, doc) in TESTS.items():
            print(f"{name:18s} {doc}")
        return
    names = list(TESTS) if args.tests == ["all"] else args.tests
    unknown = [n for n in names if n not in TESTS]
    if unknown:
        sys.exit(f"unknown tests: {unknown}")
    out_dir = REPO / "hitl_logs" / f"drive_hb_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True)
    sys.exit(run(names, out_dir))


if __name__ == "__main__":
    main()
