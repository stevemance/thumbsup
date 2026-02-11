#!/usr/bin/env python3
"""
ThumbsUp HITL orchestrator.

Goals:
- Build + flash the HITL robot firmware (Bluetooth competition path + HITL console)
- Build + flash the HITL gamepad emulator firmware
- Run an automated test suite with pass/fail and artifacts

The orchestrator prefers stable udev symlinks:
  - /dev/ttyHITL_ROBOT
  - /dev/ttyHITL_GAMEPAD
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    print(f"Missing pyserial: {exc}")
    sys.exit(1)

from common import HITL_STATUS_RE, parse_kv_payload, run_cmd, slugify

HITL_EVENT_RE = re.compile(r"^HITL EVENT (.+)$")
HITL_BTADDR_RE = re.compile(r"^HITL BTADDR ([0-9A-Fa-f:]{17})$")
LSUSB_RP2_BOOT_RE = re.compile(r"^Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+2e8a:0003\b")


def lsusb_rp2_bootsel_devices() -> set[tuple[int, int]]:
    """Return {(bus, address)} for all connected RP2 BOOTSEL devices (2e8a:0003)."""
    result = run_cmd(["lsusb"], check=True, capture_output=True)
    out: set[tuple[int, int]] = set()
    for line in (result.stdout or "").splitlines():
        m = LSUSB_RP2_BOOT_RE.match(line.strip())
        if not m:
            continue
        out.add((int(m.group(1)), int(m.group(2))))
    return out


def wait_for_new_rp2_bootsel_device(before: set[tuple[int, int]], timeout_s: float) -> tuple[int, int]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        now = lsusb_rp2_bootsel_devices()
        new = now - before
        if len(new) == 1:
            return next(iter(new))
        time.sleep(0.05)
    raise RuntimeError("timeout waiting for RP2 BOOTSEL device to appear")


def udev_props(dev: str) -> dict[str, str]:
    result = run_cmd(["udevadm", "info", "-q", "property", "-n", dev], check=True, capture_output=True)
    props: dict[str, str] = {}
    for line in (result.stdout or "").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def find_port_by_symlink(path: str) -> str | None:
    p = Path(path)
    if p.exists():
        return str(p)
    return None


def find_port_by_product(product_hint: str) -> str | None:
    hint = product_hint.lower()
    for port in serial.tools.list_ports.comports():
        product = (port.product or "").lower()
        description = (port.description or "").lower()
        if hint in product or hint in description:
            return port.device
    return None


def resolve_robot_port(timeout_s: float = 10.0) -> str:
    deadline = time.time() + max(0.1, float(timeout_s))
    while time.time() < deadline:
        port = find_port_by_symlink("/dev/ttyHITL_ROBOT")
        if port:
            return port
        port = find_port_by_product("ThumbsUp HITL Robot")
        if port:
            return port
        time.sleep(0.1)
    raise RuntimeError("could not find robot serial port (expected /dev/ttyHITL_ROBOT or USB product match)")


def resolve_gamepad_port(timeout_s: float = 10.0) -> str:
    deadline = time.time() + max(0.1, float(timeout_s))
    while time.time() < deadline:
        port = find_port_by_symlink("/dev/ttyHITL_GAMEPAD")
        if port:
            return port
        port = find_port_by_product("ThumbsUp HITL Gamepad")
        if port:
            return port
        time.sleep(0.1)
    raise RuntimeError("could not find gamepad serial port (expected /dev/ttyHITL_GAMEPAD or USB product match)")


def get_usb_serial_for_tty(dev: str) -> str:
    props = udev_props(dev)
    serial_short = props.get("ID_SERIAL_SHORT")
    if not serial_short:
        raise RuntimeError(f"could not read ID_SERIAL_SHORT for {dev}")
    return serial_short


def wait_for_path(path: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if Path(path).exists():
            return
        time.sleep(0.1)
    raise RuntimeError(f"timeout waiting for {path}")


def wait_for_tty_ready(path: str, timeout_s: float) -> None:
    wait_for_path(path, timeout_s)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with serial.Serial(path, 115200, timeout=0.05, write_timeout=0.2):
                return
        except serial.SerialException:
            time.sleep(0.1)
    raise RuntimeError(f"timeout waiting for serial port to open: {path}")


def wait_for_tty_reenumerate(path: str, timeout_s: float) -> None:
    # picotool "force reboot" can return before the host tty fully cycles.
    # Wait for the port to disappear at least once (if it does), then wait until it is openable.
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not Path(path).exists():
            break
        time.sleep(0.05)
    remaining = max(0.1, deadline - time.time())
    wait_for_tty_ready(path, remaining)


def picotool_flash_via_reset(usb_serial: str, uf2_path: str, *, log_path: Path | None = None) -> None:
    if not Path(uf2_path).exists():
        raise RuntimeError(f"missing UF2: {uf2_path}")

    before = lsusb_rp2_bootsel_devices()
    reboot = run_cmd(["picotool", "reboot", "-u", "-f", "--ser", usb_serial], check=True, capture_output=True)
    bus, addr = wait_for_new_rp2_bootsel_device(before, timeout_s=10.0)
    load = run_cmd(
        ["picotool", "load", "-x", uf2_path, "--bus", str(bus), "--address", str(addr)],
        check=True,
        capture_output=True,
    )
    if log_path is not None:
        lines = []
        lines.append(f"picotool reboot -u -f --ser {usb_serial}")
        if reboot.stdout:
            lines.append(reboot.stdout.strip())
        if reboot.stderr:
            lines.append(reboot.stderr.strip())
        lines.append(f"picotool load -x {uf2_path} --bus {bus} --address {addr}")
        if load.stdout:
            lines.append(load.stdout.strip())
        if load.stderr:
            lines.append(load.stderr.strip())
        log_path.write_text("\n".join(l for l in lines if l) + "\n", encoding="utf-8")


def picotool_reboot_application(usb_serial: str) -> None:
    # Start tests from a clean state (clears any latched safety/ESTOP state).
    # Uses picotool's "force" path so we don't need BOOTSEL or a power cycle.
    run_cmd(["picotool", "reboot", "-a", "-f", "--ser", usb_serial], check=True, capture_output=True)


def build_robot(repo_root: Path) -> None:
    run_cmd([str(repo_root / "tools" / "build.sh")], check=True, capture_output=False)


def build_gamepad(repo_root: Path) -> None:
    env = os.environ.copy()
    if "PICO_SDK_PATH" not in env or not env["PICO_SDK_PATH"]:
        env["PICO_SDK_PATH"] = str(Path.home() / "pico" / "pico-sdk")
    build_dir = repo_root / "controller_emulator" / "build"
    run_cmd(
        ["cmake", "-S", str(repo_root / "controller_emulator"), "-B", str(build_dir)],
        check=True,
        capture_output=True,
        env=env,
    )
    run_cmd(
        ["cmake", "--build", str(build_dir), "-j", str(os.cpu_count() or 4)],
        check=True,
        capture_output=False,
        env=env,
    )


def labctl_psu_off(channel: int) -> None:
    run_cmd(["labctl", "psu", "off", "--channel", str(channel)], check=False, capture_output=True)


def labctl_psu_set(channel: int, voltage: float, current: float) -> None:
    run_cmd(
        [
            "labctl",
            "psu",
            "set",
            "--channel",
            str(channel),
            "--voltage",
            str(voltage),
            "--current",
            str(current),
            "--on",
        ],
        check=True,
        capture_output=True,
    )


def labctl_psu_snapshot(channel: int) -> dict:
    result = run_cmd(["labctl", "--json", "psu", "snapshot", "--channel", str(channel)], check=True, capture_output=True)
    payload = json.loads(result.stdout or "{}")
    return payload


def labctl_psu_measure(channel: int, kind: str) -> float | None:
    # Use --json for stable parsing. Return None on any error/timeouts.
    result = run_cmd(
        ["labctl", "--json", "--timeout", "2.0", "psu", "measure", "--channel", str(channel), "--kind", kind],
        check=False,
        capture_output=True,
    )
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not payload.get("ok"):
        return None
    text = payload.get("text")
    if text is None:
        return None
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str
    started_at: str
    finished_at: str
    artifacts_dir: str | None = None


class SerialLogger:
    def __init__(self, ser: serial.Serial, log_path: Path, label: str):
        self._ser = ser
        self._log_path = log_path
        self._label = label
        self._start = time.monotonic()
        self._handle = log_path.open("w", encoding="utf-8")

    def close(self) -> None:
        try:
            self._handle.close()
        except Exception:
            pass

    def write_tx(self, line: str) -> None:
        t_s = time.monotonic() - self._start
        self._handle.write(f"{t_s:9.3f}\t{self._label}\tTX\t{line}\n")
        self._handle.flush()

    def write_rx(self, line: str) -> None:
        t_s = time.monotonic() - self._start
        self._handle.write(f"{t_s:9.3f}\t{self._label}\tRX\t{line}\n")
        self._handle.flush()

    def send_line(self, line: str) -> None:
        self._ser.write((line + "\n").encode("utf-8"))
        self._ser.flush()
        self.write_tx(line)

    def read_line(self) -> str | None:
        # Avoid blocking when there's no pending RX data.
        try:
            if self._ser.in_waiting == 0:
                return None
        except Exception:
            # Fall back to readline() if in_waiting isn't supported.
            pass

        raw = self._ser.readline()
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace").rstrip()
        if text:
            self.write_rx(text)
        return text


def wait_for_robot_btaddr(robot_log: SerialLogger, timeout_s: float) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        line = robot_log.read_line()
        if not line:
            time.sleep(0.01)
            continue
        m = HITL_BTADDR_RE.match(line)
        if m:
            return m.group(1)
    raise RuntimeError("timeout waiting for HITL BTADDR response")


def wait_for_robot_condition(
    robot_log: SerialLogger,
    *,
    timeout_s: float,
    predicate,
    pump_logs: list[SerialLogger] | None = None,
) -> dict[str, str]:
    deadline = time.monotonic() + timeout_s
    last_status: dict[str, str] = {}
    while time.monotonic() < deadline:
        if pump_logs:
            for log in pump_logs:
                log.read_line()
        line = robot_log.read_line()
        if not line:
            time.sleep(0.01)
            continue
        m = HITL_STATUS_RE.match(line)
        if m:
            last_status = parse_kv_payload(m.group(1))
            if predicate(last_status):
                return last_status
        m = HITL_EVENT_RE.match(line)
        if m:
            # Allow predicates to match on events as well by stashing event kvs.
            last_status = {**last_status, **parse_kv_payload(m.group(1))}
            if predicate(last_status):
                return last_status
    raise RuntimeError(f"timeout waiting for robot condition; last_status={last_status}")


def ensure_robot_ready(robot_log: SerialLogger, gamepad_log: SerialLogger, *, timeout_s: float) -> None:
    # Tear down any lingering BT connection from a previous run before
    # attempting a fresh connect.  Without this, the robot's BT stack may
    # see a stale/half-open link and fail to process the new pairing.
    gamepad_log.send_line("DISCONNECT")
    # Wait for the BT disconnect to actually complete (emulator prints
    # "HID disconnected" when L2CAP teardown finishes), not just ACK.
    disc_deadline = time.monotonic() + 2.0
    while time.monotonic() < disc_deadline:
        line = gamepad_log.read_line()
        if line and "HID disconnected" in line:
            break
        robot_log.read_line()  # drain robot too
        if not line:
            time.sleep(0.01)
    time.sleep(0.1)

    gamepad_log.send_line("RESET")

    robot_log.send_line("HITL BTADDR")
    btaddr = wait_for_robot_btaddr(robot_log, timeout_s=5.0)

    def wait_ready(t: float) -> None:
        wait_for_robot_condition(
            robot_log,
            timeout_s=t,
            predicate=lambda s: s.get("ready") == "1" and s.get("conn") == "1",
            pump_logs=[gamepad_log],
        )

    # Attempt 1: use existing keys (most stable / fastest).
    gamepad_log.send_line(f"CONNECT {btaddr}")
    try:
        wait_ready(timeout_s)
        return
    except RuntimeError:
        pass

    # Attempt 2: wipe keys on both sides to force a clean pair.
    robot_log.send_line("HITL BTKEYS CLEAR")
    gamepad_log.send_line("DISCONNECT")
    gamepad_log.send_line("KEYS CLEAR")
    time.sleep(0.8)
    gamepad_log.send_line(f"CONNECT {btaddr}")
    wait_ready(timeout_s * 3.0)


def step(name: str):
    def deco(fn):
        def wrapped(*args, **kwargs):
            out_dir = kwargs.get("out_dir")
            artifacts_dir = str(out_dir) if out_dir is not None else None
            started = now_iso()
            try:
                detail = fn(*args, **kwargs)
                return StepResult(
                    name=name,
                    ok=True,
                    detail=detail or "ok",
                    started_at=started,
                    finished_at=now_iso(),
                    artifacts_dir=artifacts_dir,
                )
            except Exception as exc:
                return StepResult(
                    name=name,
                    ok=False,
                    detail=str(exc),
                    started_at=started,
                    finished_at=now_iso(),
                    artifacts_dir=artifacts_dir,
                )
        return wrapped
    return deco


@step("Build Firmware")
def do_build(repo_root: Path, build_robot_fw: bool, build_gamepad_fw: bool, out_dir: Path | None = None) -> str:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    if build_robot_fw:
        if out_dir is None:
            build_robot(repo_root)
        else:
            result = run_cmd([str(repo_root / "tools" / "build.sh")], check=True, capture_output=True)
            (out_dir / "build_robot.log").write_text(
                (result.stdout or "") + ("\n" + result.stderr if result.stderr else ""),
                encoding="utf-8",
            )

    if build_gamepad_fw:
        if out_dir is None:
            build_gamepad(repo_root)
        else:
            env = os.environ.copy()
            if "PICO_SDK_PATH" not in env or not env["PICO_SDK_PATH"]:
                env["PICO_SDK_PATH"] = str(Path.home() / "pico" / "pico-sdk")
            build_dir = repo_root / "controller_emulator" / "build"

            cfg = run_cmd(
                ["cmake", "-S", str(repo_root / "controller_emulator"), "-B", str(build_dir)],
                check=True,
                capture_output=True,
                env=env,
            )
            (out_dir / "build_gamepad_configure.log").write_text(
                (cfg.stdout or "") + ("\n" + cfg.stderr if cfg.stderr else ""),
                encoding="utf-8",
            )

            bld = run_cmd(
                ["cmake", "--build", str(build_dir), "-j", str(os.cpu_count() or 4)],
                check=True,
                capture_output=True,
                env=env,
            )
            (out_dir / "build_gamepad_build.log").write_text(
                (bld.stdout or "") + ("\n" + bld.stderr if bld.stderr else ""),
                encoding="utf-8",
            )
    return "built"


@step("Flash Firmware")
def do_flash(repo_root: Path, flash_robot: bool, flash_gamepad: bool, out_dir: Path | None = None) -> str:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        flash_log = out_dir / "flash.log"
    else:
        flash_log = None

    # Resolve current tty devices to read their application-mode USB serials.
    if flash_robot:
        robot_tty = resolve_robot_port()
        robot_usb_ser = get_usb_serial_for_tty(robot_tty)
        if flash_log is not None:
            flash_log.write_text(
                f"robot_tty={robot_tty}\nrobot_usb_serial={robot_usb_ser}\n",
                encoding="utf-8",
            )
        picotool_flash_via_reset(
            robot_usb_ser,
            str(repo_root / "firmware" / "build" / "thumbsup_hitl.uf2"),
            log_path=(out_dir / "picotool_robot.log") if out_dir is not None else None,
        )
        wait_for_tty_ready("/dev/ttyHITL_ROBOT", 10)

    if flash_gamepad:
        gamepad_tty = resolve_gamepad_port()
        gamepad_usb_ser = get_usb_serial_for_tty(gamepad_tty)
        if flash_log is not None:
            flash_log.write_text(
                (flash_log.read_text(encoding="utf-8") if flash_log.exists() else "")
                + f"gamepad_tty={gamepad_tty}\ngamepad_usb_serial={gamepad_usb_ser}\n",
                encoding="utf-8",
            )
        picotool_flash_via_reset(
            gamepad_usb_ser,
            str(repo_root / "controller_emulator" / "build" / "thumbsup_controller_emulator.uf2"),
            log_path=(out_dir / "picotool_gamepad.log") if out_dir is not None else None,
        )
        wait_for_tty_ready("/dev/ttyHITL_GAMEPAD", 10)

    return "flashed"


@step("Smoke Test")
def do_smoke(repo_root: Path, psu_channel: int | None, psu_off_first: bool, out_dir: Path | None = None) -> str:
    if psu_channel is not None and psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start the suite from a known state.
    # This avoids "sticky" safety/weapon emergency-stop conditions persisting across runs.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")

        # Drain startup noise.
        start = time.monotonic()
        while time.monotonic() - start < 3.0:
            robot_log.read_line()
            gamepad_log.read_line()

        # Wait for at least one status sample so we know the HITL console tick is alive.
        wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

        # Force a safe, deterministic battery voltage for HITL.
        robot_log.send_line("HITL BATTERY 12500")
        wait_for_robot_condition(
            robot_log,
            timeout_s=3.0,
            predicate=lambda s: s.get("batt_mv") == "12500",
            pump_logs=[gamepad_log],
        )

        ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)
        # Allow the robot-side neutral-sticks guard (500ms) to clear before arming.
        time.sleep(0.7)

        # Arm toggle with B.
        gamepad_log.send_line("BTN B 1")
        time.sleep(0.1)
        gamepad_log.send_line("BTN B 0")
        wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1")

        # Emergency stop with L1+R1.
        gamepad_log.send_line("BTN L1 1")
        gamepad_log.send_line("BTN R1 1")
        wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("failsafe") == "1")
        gamepad_log.send_line("BTN L1 0")
        gamepad_log.send_line("BTN R1 0")

        # Clear estop by holding A for SAFETY_BUTTON_HOLD_TIME (2s) + margin.
        gamepad_log.send_line("BTN A 1")
        time.sleep(2.3)
        gamepad_log.send_line("BTN A 0")
        wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("failsafe") == "0")

        # Re-arm + disarm to validate the full toggle path.
        gamepad_log.send_line("BTN B 1")
        time.sleep(0.1)
        gamepad_log.send_line("BTN B 0")
        wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1")

        # Respect debounce timing in firmware (DEBOUNCE_TIME_MS=100).
        time.sleep(0.2)

        gamepad_log.send_line("BTN B 1")
        time.sleep(0.1)
        gamepad_log.send_line("BTN B 0")
        wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "0")

        # Explicit status snapshot for the logs.
        robot_log.send_line("HITL STATUS")
        time.sleep(0.3)
        for _ in range(30):
            robot_log.read_line()

        # PSU snapshot, if available.
        if psu_channel is not None:
            try:
                payload = labctl_psu_snapshot(psu_channel)
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
            (out_dir / "psu_snapshot.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )

        robot_log.close()
        gamepad_log.close()

    return "smoke passed"


@step("Drive E2E Test")
def do_drive_e2e(
    repo_root: Path,
    psu_channel: int | None,
    psu_off_first: bool,
    drive_forward_axis: int,
    drive_turn_axis: int,
    drive_hold_s: float,
    drive_min_delta_us: int,
    out_dir: Path | None = None,
) -> str:
    # This suite does not require the PSU, but turning it off first can avoid surprises.
    if psu_channel is not None and psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start the suite from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")

        drive_states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS LX 0")
                gamepad_log.send_line("AXIS LY 0")
                gamepad_log.send_line("AXIS RX 0")
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
                gamepad_log.send_line("BTN L3 0")
                gamepad_log.send_line("BTN R3 0")
            except Exception:
                pass

        def get_pulses(s: dict[str, str]) -> tuple[int, int]:
            dl = int(s.get("dl_us") or 0)
            dr = int(s.get("dr_us") or 0)
            return dl, dr

        def near_neutral(s: dict[str, str], *, tol_us: int = 25) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) <= tol_us and abs(dr - 1500) <= tol_us

        def deviated(s: dict[str, str], *, min_delta_us: int) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) >= min_delta_us and abs(dr - 1500) >= min_delta_us

        def same_side(s: dict[str, str]) -> bool:
            dl, dr = get_pulses(s)
            return (dl - 1500) * (dr - 1500) > 0

        def opposite_side(s: dict[str, str]) -> bool:
            dl, dr = get_pulses(s)
            return (dl - 1500) * (dr - 1500) < 0

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            # Put both devices into a deterministic state.
            gamepad_log.send_line("RESET")

            # Wait for at least one status sample so we know the HITL console tick is alive.
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            # Wait until failsafe clears (no estop, recent controller activity).
            wait_for_robot_condition(
                robot_log,
                timeout_s=5.0,
                predicate=lambda s: s.get("failsafe") == "0",
                pump_logs=[gamepad_log],
            )

            drive_hold_s = max(0.2, float(drive_hold_s))
            drive_forward_axis = max(-127, min(127, int(drive_forward_axis)))
            drive_turn_axis = max(-127, min(127, int(drive_turn_axis)))

            # Baseline: sticks neutral -> neutral pulses.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            s0 = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: near_neutral(s, tol_us=30))
            drive_states["neutral"] = s0

            # Forward: LY negative (competition code treats negative Y as forward).
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line(f"AXIS LY {drive_forward_axis}")
            s_fwd = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=drive_min_delta_us) and opposite_side(s),
            )
            drive_states["forward"] = s_fwd
            time.sleep(drive_hold_s)

            # Turn in place: LX non-zero, LY 0. Expect both pulses on same side of neutral.
            gamepad_log.send_line("AXIS LY 0")
            gamepad_log.send_line(f"AXIS LX {drive_turn_axis}")
            s_turn = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=drive_min_delta_us) and same_side(s),
            )
            drive_states["turn"] = s_turn
            time.sleep(drive_hold_s)

            # Stop: back to neutral.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            s_stop = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=40))
            drive_states["stop"] = s_stop

            # Validate emergency stop halts drive outputs.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line(f"AXIS LY {drive_forward_axis}")
            wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=drive_min_delta_us),
            )
            gamepad_log.send_line("BTN L1 1")
            gamepad_log.send_line("BTN R1 1")
            s_estop = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("failsafe") == "1")
            drive_states["estop"] = s_estop
            # Drive should settle back to neutral after estop.
            s_estop_stop = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=50))
            drive_states["estop_stop"] = s_estop_stop
            gamepad_log.send_line("BTN L1 0")
            gamepad_log.send_line("BTN R1 0")
            gamepad_log.send_line("AXIS LY 0")

            # Clear estop by holding A for SAFETY_BUTTON_HOLD_TIME (2s) + margin.
            gamepad_log.send_line("BTN A 1")
            time.sleep(2.3)
            gamepad_log.send_line("BTN A 0")
            s_clear = wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("failsafe") == "0")
            drive_states["estop_clear"] = s_clear

            # Final neutral.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            s_final = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=40))
            drive_states["final"] = s_final

            (out_dir / "drive_e2e_result.json").write_text(
                json.dumps(
                    {
                        "drive_forward_axis": drive_forward_axis,
                        "drive_turn_axis": drive_turn_axis,
                        "drive_hold_s": drive_hold_s,
                        "drive_min_delta_us": drive_min_delta_us,
                        "states": drive_states,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        finally:
            try:
                psu_stop.set()
                if psu_thread is not None:
                    psu_thread.join(timeout=3.0)
            except Exception:
                pass
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "drive e2e passed"


@step("Disconnect Failsafe Test")
def do_disconnect_failsafe(
    repo_root: Path,
    psu_channel: int | None,
    psu_off_first: bool,
    drive_forward_axis: int,
    drive_min_delta_us: int,
    out_dir: Path | None = None,
) -> str:
    # This suite does not require the PSU, but turning it off first can avoid surprises.
    if psu_channel is not None and psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start the suite from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")

        states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS LX 0")
                gamepad_log.send_line("AXIS LY 0")
                gamepad_log.send_line("AXIS RX 0")
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
            except Exception:
                pass

        def get_pulses(s: dict[str, str]) -> tuple[int, int]:
            dl = int(s.get("dl_us") or 0)
            dr = int(s.get("dr_us") or 0)
            return dl, dr

        def near_neutral(s: dict[str, str], *, tol_us: int = 25) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) <= tol_us and abs(dr - 1500) <= tol_us

        def deviated(s: dict[str, str], *, min_delta_us: int) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) >= min_delta_us and abs(dr - 1500) >= min_delta_us

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            # Put both devices into a deterministic state.
            gamepad_log.send_line("RESET")

            # Wait for at least one status sample so we know the HITL console tick is alive.
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            # Wait until failsafe clears (no estop, recent controller activity).
            wait_for_robot_condition(
                robot_log,
                timeout_s=5.0,
                predicate=lambda s: s.get("failsafe") == "0",
                pump_logs=[gamepad_log],
            )

            drive_forward_axis = max(-127, min(127, int(drive_forward_axis)))

            # Start driving so we can assert the disconnect drives outputs back to neutral.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line(f"AXIS LY {drive_forward_axis}")
            s_move = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=drive_min_delta_us),
                pump_logs=[gamepad_log],
            )
            states["moving"] = s_move

            # Disconnect controller.
            gamepad_log.send_line("DISCONNECT")
            s_disc = wait_for_robot_condition(
                robot_log,
                timeout_s=10.0,
                predicate=lambda s: s.get("conn") == "0" and s.get("failsafe") == "1",
                pump_logs=[gamepad_log],
            )
            states["disconnected"] = s_disc

            # Outputs should settle back to neutral.
            s_stop = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: near_neutral(s, tol_us=60),
                pump_logs=[gamepad_log],
            )
            states["neutral_after_disconnect"] = s_stop

            # Reconnect should clear failsafe (my_platform_on_device_ready clears emergency_stop).
            ensure_robot_ready(robot_log, gamepad_log, timeout_s=60.0)
            s_reconn = wait_for_robot_condition(
                robot_log,
                timeout_s=8.0,
                predicate=lambda s: s.get("conn") == "1" and s.get("ready") == "1" and s.get("failsafe") == "0",
                pump_logs=[gamepad_log],
            )
            states["reconnected"] = s_reconn

            (out_dir / "disconnect_failsafe_result.json").write_text(
                json.dumps(
                    {
                        "drive_forward_axis": drive_forward_axis,
                        "drive_min_delta_us": drive_min_delta_us,
                        "states": states,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "disconnect failsafe passed"


@step("Drive Spin Test")
def do_drive_spin(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    drive_forward_axis: int,
    drive_turn_axis: int,
    drive_hold_s: float,
    drive_sample_interval_s: float,
    drive_settle_s: float,
    drive_current_delta_a: float,
    drive_min_current_a: float,
    drive_return_tol_a: float,
    out_dir: Path | None = None,
) -> str:
    if psu_channel is None:
        raise RuntimeError("psu_channel is required for drive_spin")

    if psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start the suite from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    # Power motor supply and require it to be on.
    labctl_psu_set(psu_channel, psu_voltage, psu_current)
    # Best-effort status check: USBTMC can be flaky; if snapshot fails we rely on the
    # subsequent current sampling to fail the test when the PSU is truly off.
    snap: dict | None = None
    for attempt in range(3):
        try:
            snap = labctl_psu_snapshot(psu_channel)
            break
        except Exception:
            time.sleep(0.15 * (attempt + 1))
    if snap is not None:
        try:
            status = str(((snap.get("values") or {}).get(str(psu_channel)) or {}).get("status") or "").upper()
        except Exception:
            status = ""
        if status and status != "ON":
            raise RuntimeError(f"PSU channel {psu_channel} is not ON (snapshot={snap})")

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        psu_samples: list[dict] = []
        states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS LX 0")
                gamepad_log.send_line("AXIS LY 0")
                gamepad_log.send_line("AXIS RX 0")
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
            except Exception:
                pass
            if not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        def psu_sample_current(phase: str) -> float | None:
            value = labctl_psu_measure(psu_channel, "current")
            psu_samples.append(
                {
                    "t_s": round(time.monotonic() - suite_t0, 3),
                    "phase": phase,
                    "current_a": value,
                }
            )
            return value

        def drain_robot_serial(max_s: float) -> None:
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if not line:
                    break

        def sample_current_window(phase: str, duration_s: float, *, settle_s: float = 0.0) -> list[float]:
            values: list[float] = []
            duration_s = max(0.0, float(duration_s))
            settle_s = max(0.0, float(settle_s))
            start_t = time.monotonic()
            next_sample = start_t
            while True:
                now = time.monotonic()
                elapsed = now - start_t
                if elapsed >= duration_s:
                    break
                drain_robot_serial(0.02)
                if now < next_sample:
                    time.sleep(min(0.01, next_sample - now))
                    continue
                current = psu_sample_current(phase)
                if current is not None and elapsed >= settle_s:
                    values.append(current)
                next_sample += max(0.05, float(drive_sample_interval_s))
            return values

        def get_pulses(s: dict[str, str]) -> tuple[int, int]:
            dl = int(s.get("dl_us") or 0)
            dr = int(s.get("dr_us") or 0)
            return dl, dr

        def near_neutral(s: dict[str, str], *, tol_us: int = 25) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) <= tol_us and abs(dr - 1500) <= tol_us

        def deviated(s: dict[str, str], *, min_delta_us: int) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) >= min_delta_us and abs(dr - 1500) >= min_delta_us

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")

            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            wait_for_robot_condition(
                robot_log,
                timeout_s=5.0,
                predicate=lambda s: s.get("failsafe") == "0",
                pump_logs=[gamepad_log],
            )

            drive_forward_axis = max(-127, min(127, int(drive_forward_axis)))
            drive_turn_axis = max(-127, min(127, int(drive_turn_axis)))
            drive_hold_s = max(0.6, float(drive_hold_s))

            # Baseline: neutral sticks.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            s0 = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: near_neutral(s, tol_us=35), pump_logs=[gamepad_log])
            states["neutral"] = s0
            baseline_values = sample_current_window("baseline", 1.5, settle_s=0.0)
            baseline_med = statistics.median(baseline_values) if baseline_values else None
            if baseline_med is None:
                raise RuntimeError("no PSU current samples for baseline")

            # Individual drive checks: command each side independently by canceling one motor in the mixer.
            #
            # Rationale: Total PSU current is a strong "did anything spin" signal, but with both drive
            # motors commanded together it can pass even if one motor is unplugged. We therefore run
            # "left-only" and "right-only" phases where one side is held near neutral (1500us).

            def clamp_axis(v: int) -> int:
                return max(-127, min(127, int(v)))

            # Avoid saturating the mixer when trying to cancel one side. With default config
            # (MAX_DRIVE_SPEED > MAX_TURN_SPEED), extreme forward values can prevent perfect cancel.
            single_forward_axis = drive_forward_axis
            if abs(single_forward_axis) > 110:
                single_forward_axis = 110 if single_forward_axis > 0 else -110

            def find_single_side_lx(stop_side: str, ly: int) -> tuple[int, dict[str, str]]:
                """
                Find an LX value that keeps the requested stop_side motor near neutral while LY is held.

                stop_side: "left" or "right" (which motor should be ~1500us)
                Returns: (lx, status_dict)
                """
                ly = clamp_axis(ly)
                if stop_side not in ("left", "right"):
                    raise ValueError(f"invalid stop_side: {stop_side}")

                # Best-effort guess from firmware defaults (MAX_DRIVE_SPEED=75, MAX_TURN_SPEED=70).
                # Even if these change, the scan below will still find a reasonable cancel point.
                ratio = 75.0 / 70.0
                guess = int(round(ly * ratio))
                if stop_side == "left":
                    # left=F+T => cancel left by T=-F
                    guess = -guess

                def score_for(s: dict[str, str], lx: int) -> tuple[int, int, int]:
                    dl, dr = get_pulses(s)
                    stop_pulse = dl if stop_side == "left" else dr
                    active_pulse = dr if stop_side == "left" else dl
                    stop_delta = abs(stop_pulse - 1500)
                    active_delta = abs(active_pulse - 1500)
                    # Sort by: stop delta (smaller is better), then active delta (larger is better),
                    # then |lx| (prefer smaller turns to reduce trim interactions).
                    return (stop_delta, -active_delta, abs(lx))

                def try_lx_values(cands: list[int]) -> tuple[int, dict[str, str]] | None:
                    best: tuple[tuple[int, int, int], int, dict[str, str]] | None = None
                    for lx in cands:
                        lx = clamp_axis(lx)
                        gamepad_log.send_line(f"AXIS LX {lx}")
                        gamepad_log.send_line(f"AXIS LY {ly}")
                        try:
                            # Wait for any meaningful deviation on the active side before scoring.
                            if stop_side == "right":
                                pred = lambda s: abs(int(s.get("dl_us") or 0) - 1500) >= 60
                            else:
                                pred = lambda s: abs(int(s.get("dr_us") or 0) - 1500) >= 60
                            s = wait_for_robot_condition(
                                robot_log,
                                timeout_s=0.8,
                                predicate=pred,
                                pump_logs=[gamepad_log],
                            )
                        except RuntimeError:
                            continue

                        sc = score_for(s, lx)
                        if best is None or sc < best[0]:
                            best = (sc, lx, s)
                            # If we nailed a very small stop delta, stop searching early.
                            if sc[0] <= 15:
                                break
                    if best is None:
                        return None
                    return best[1], best[2]

                span = 48
                step = 4
                near = list(range(guess - span, guess + span + 1, step))
                found = try_lx_values(near)
                if found is not None:
                    return found

                # Fallback: full scan (coarser) if the guess window didn't find a good candidate.
                full = list(range(-127, 128, 6))
                found = try_lx_values(full)
                if found is None:
                    raise RuntimeError(f"could not find single-side cancel (stop_side={stop_side} ly={ly})")
                return found

            # Left-only (right motor canceled).
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            lx_left, s_left = find_single_side_lx("right", single_forward_axis)
            states["left_only"] = s_left
            left_values = sample_current_window("left_only", drive_hold_s, settle_s=drive_settle_s)
            left_med = statistics.median(left_values) if left_values else None

            # Stop after left-only.
            gamepad_log.send_line("AXIS LY 0")
            gamepad_log.send_line("AXIS LX 0")
            s_stop_left = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            states["stop_left"] = s_stop_left
            stop_left_values = sample_current_window("stop_left", 1.0, settle_s=0.0)
            stop_left_med = statistics.median(stop_left_values) if stop_left_values else None

            # Right-only (left motor canceled).
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            lx_right, s_right = find_single_side_lx("left", single_forward_axis)
            states["right_only"] = s_right
            right_values = sample_current_window("right_only", drive_hold_s, settle_s=drive_settle_s)
            right_med = statistics.median(right_values) if right_values else None

            # Stop after right-only.
            gamepad_log.send_line("AXIS LY 0")
            gamepad_log.send_line("AXIS LX 0")
            s_stop_right = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            states["stop_right"] = s_stop_right
            stop_right_values = sample_current_window("stop_right", 1.0, settle_s=0.0)
            stop_right_med = statistics.median(stop_right_values) if stop_right_values else None

            # Forward run.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line(f"AXIS LY {drive_forward_axis}")
            s_fwd = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=60),
                pump_logs=[gamepad_log],
            )
            states["forward"] = s_fwd
            fwd_values = sample_current_window("forward", drive_hold_s, settle_s=drive_settle_s)
            fwd_med = statistics.median(fwd_values) if fwd_values else None

            # Stop.
            gamepad_log.send_line("AXIS LY 0")
            s_stop1 = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            states["stop1"] = s_stop1
            stop1_values = sample_current_window("stop1", 1.0, settle_s=0.0)
            stop1_med = statistics.median(stop1_values) if stop1_values else None

            # Turn run (in-place).
            gamepad_log.send_line("AXIS LY 0")
            gamepad_log.send_line(f"AXIS LX {drive_turn_axis}")
            s_turn = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=60),
                pump_logs=[gamepad_log],
            )
            states["turn"] = s_turn
            turn_values = sample_current_window("turn", drive_hold_s, settle_s=drive_settle_s)
            turn_med = statistics.median(turn_values) if turn_values else None

            # Stop again.
            gamepad_log.send_line("AXIS LX 0")
            s_stop2 = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            states["stop2"] = s_stop2
            stop2_values = sample_current_window("stop2", 1.0, settle_s=0.0)
            stop2_med = statistics.median(stop2_values) if stop2_values else None

            def ok_run(run_med: float | None) -> tuple[bool, float | None]:
                if run_med is None:
                    return False, None
                delta = run_med - baseline_med
                ok = (delta >= float(drive_current_delta_a)) and (run_med >= float(drive_min_current_a))
                return ok, delta

            fwd_ok, fwd_delta = ok_run(fwd_med)
            turn_ok, turn_delta = ok_run(turn_med)
            left_ok, left_delta = ok_run(left_med)
            right_ok, right_delta = ok_run(right_med)

            def tail_median(values: list[float], n: int = 3) -> float | None:
                if not values:
                    return None
                n = max(1, min(int(n), len(values)))
                return statistics.median(values[-n:])

            stop1_tail_med = tail_median(stop1_values, n=3)
            stop2_tail_med = tail_median(stop2_values, n=3)
            stop_left_tail_med = tail_median(stop_left_values, n=3)
            stop_right_tail_med = tail_median(stop_right_values, n=3)

            def ok_return(stop_tail_med: float | None) -> bool:
                if stop_tail_med is None:
                    return False
                return abs(stop_tail_med - baseline_med) <= float(drive_return_tol_a)

            stop1_ok = ok_return(stop1_tail_med)
            stop2_ok = ok_return(stop2_tail_med)
            stop_left_ok = ok_return(stop_left_tail_med)
            stop_right_ok = ok_return(stop_right_tail_med)

            result = {
                "ok": bool(left_ok and right_ok and fwd_ok and turn_ok and stop_left_ok and stop_right_ok and stop1_ok and stop2_ok),
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "drive_forward_axis": drive_forward_axis,
                "drive_turn_axis": drive_turn_axis,
                "single_forward_axis": single_forward_axis,
                "drive_hold_s": drive_hold_s,
                "drive_settle_s": float(drive_settle_s),
                "thresholds": {
                    "delta_a": float(drive_current_delta_a),
                    "min_current_a": float(drive_min_current_a),
                    "return_tol_a": float(drive_return_tol_a),
                },
                "baseline": {"median_a": baseline_med, "samples": len(baseline_values)},
                "left_only": {
                    "axis": {"lx": lx_left, "ly": single_forward_axis},
                    "median_a": left_med,
                    "delta_a": left_delta,
                    "ok": left_ok,
                    "samples": len(left_values),
                },
                "right_only": {
                    "axis": {"lx": lx_right, "ly": single_forward_axis},
                    "median_a": right_med,
                    "delta_a": right_delta,
                    "ok": right_ok,
                    "samples": len(right_values),
                },
                "forward": {"median_a": fwd_med, "delta_a": fwd_delta, "ok": fwd_ok, "samples": len(fwd_values)},
                "turn": {"median_a": turn_med, "delta_a": turn_delta, "ok": turn_ok, "samples": len(turn_values)},
                "stop_left": {
                    "median_a": stop_left_med,
                    "tail_median_a": stop_left_tail_med,
                    "ok": stop_left_ok,
                    "samples": len(stop_left_values),
                },
                "stop_right": {
                    "median_a": stop_right_med,
                    "tail_median_a": stop_right_tail_med,
                    "ok": stop_right_ok,
                    "samples": len(stop_right_values),
                },
                "stop1": {
                    "median_a": stop1_med,
                    "tail_median_a": stop1_tail_med,
                    "ok": stop1_ok,
                    "samples": len(stop1_values),
                },
                "stop2": {
                    "median_a": stop2_med,
                    "tail_median_a": stop2_tail_med,
                    "ok": stop2_ok,
                    "samples": len(stop2_values),
                },
                "states": states,
            }

            (out_dir / "drive_spin_result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            (out_dir / "psu_current_samples.json").write_text(json.dumps(psu_samples, indent=2, sort_keys=True), encoding="utf-8")
            try:
                payload = labctl_psu_snapshot(psu_channel)
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
            (out_dir / "psu_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            if not result["ok"]:
                raise RuntimeError(f"drive spin not detected / not returning to baseline (result={result})")

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "drive spin passed"


@step("E-Stop While Driving Test")
def do_estop_drive(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    drive_forward_axis: int,
    drive_hold_s: float,
    drive_sample_interval_s: float,
    drive_settle_s: float,
    drive_current_delta_a: float,
    drive_min_current_a: float,
    drive_return_tol_a: float,
    out_dir: Path | None = None,
) -> str:
    """
    Assert emergency stop works while drive outputs are actively commanded.

    Signals checked:
    - Robot reports failsafe=1 and drive pulses return near neutral.
    - PSU current returns close to baseline after e-stop.
    """
    if psu_channel is None:
        raise RuntimeError("psu_channel is required for estop_drive")

    if psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    labctl_psu_set(psu_channel, psu_voltage, psu_current)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        psu_samples: list[dict] = []
        states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS LX 0")
                gamepad_log.send_line("AXIS LY 0")
                gamepad_log.send_line("AXIS RX 0")
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
            except Exception:
                pass
            if not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        def psu_sample_current(phase: str) -> float | None:
            value = labctl_psu_measure(psu_channel, "current")
            psu_samples.append(
                {
                    "t_s": round(time.monotonic() - suite_t0, 3),
                    "phase": phase,
                    "current_a": value,
                }
            )
            return value

        def drain_robot_serial(max_s: float) -> None:
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if not line:
                    break

        def sample_current_window(phase: str, duration_s: float, *, settle_s: float = 0.0) -> list[float]:
            values: list[float] = []
            duration_s = max(0.0, float(duration_s))
            settle_s = max(0.0, float(settle_s))
            start_t = time.monotonic()
            next_sample = start_t
            while True:
                now = time.monotonic()
                elapsed = now - start_t
                if elapsed >= duration_s:
                    break
                drain_robot_serial(0.02)
                if now < next_sample:
                    time.sleep(min(0.01, next_sample - now))
                    continue
                current = psu_sample_current(phase)
                if current is not None and elapsed >= settle_s:
                    values.append(current)
                next_sample += max(0.05, float(drive_sample_interval_s))
            return values

        def get_pulses(s: dict[str, str]) -> tuple[int, int]:
            dl = int(s.get("dl_us") or 0)
            dr = int(s.get("dr_us") or 0)
            return dl, dr

        def near_neutral(s: dict[str, str], *, tol_us: int = 35) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) <= tol_us and abs(dr - 1500) <= tol_us

        def deviated(s: dict[str, str], *, min_delta_us: int) -> bool:
            dl, dr = get_pulses(s)
            return abs(dl - 1500) >= min_delta_us and abs(dr - 1500) >= min_delta_us

        def tail_median(values: list[float], n: int = 3) -> float | None:
            if not values:
                return None
            n = max(1, min(int(n), len(values)))
            return statistics.median(values[-n:])

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("batt_mv") == "12500", pump_logs=[gamepad_log])

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("failsafe") == "0", pump_logs=[gamepad_log])

            drive_forward_axis = max(-127, min(127, int(drive_forward_axis)))
            drive_hold_s = max(0.6, float(drive_hold_s))

            # Baseline.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line("AXIS LY 0")
            s0 = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: near_neutral(s, tol_us=45), pump_logs=[gamepad_log])
            states["neutral"] = s0
            baseline_values = sample_current_window("baseline", 1.5, settle_s=0.0)
            baseline_med = statistics.median(baseline_values) if baseline_values else None
            if baseline_med is None:
                raise RuntimeError("no PSU current samples for baseline")

            # Start driving.
            gamepad_log.send_line("AXIS LX 0")
            gamepad_log.send_line(f"AXIS LY {drive_forward_axis}")
            s_move = wait_for_robot_condition(
                robot_log,
                timeout_s=4.0,
                predicate=lambda s: deviated(s, min_delta_us=60),
                pump_logs=[gamepad_log],
            )
            states["moving"] = s_move
            run_values = sample_current_window("drive_run", drive_hold_s, settle_s=drive_settle_s)
            run_med = statistics.median(run_values) if run_values else None

            if run_med is None:
                raise RuntimeError("no PSU current samples while driving")
            run_delta = run_med - baseline_med
            run_ok = (run_delta >= float(drive_current_delta_a)) and (run_med >= float(drive_min_current_a))

            # Emergency stop.
            gamepad_log.send_line("BTN L1 1")
            gamepad_log.send_line("BTN R1 1")
            s_estop = wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("failsafe") == "1",
                pump_logs=[gamepad_log],
            )
            states["estop"] = s_estop
            gamepad_log.send_line("BTN L1 0")
            gamepad_log.send_line("BTN R1 0")

            s_stop = wait_for_robot_condition(robot_log, timeout_s=4.0, predicate=lambda s: near_neutral(s, tol_us=60), pump_logs=[gamepad_log])
            states["neutral_after_estop"] = s_stop

            estop_values = sample_current_window("estop", 1.2, settle_s=0.2)
            estop_tail = tail_median(estop_values, n=3)
            return_ok = (estop_tail is not None) and (abs(estop_tail - baseline_med) <= float(drive_return_tol_a))

            # Clear emergency stop (hold A).
            gamepad_log.send_line("BTN A 1")
            time.sleep(2.3)
            gamepad_log.send_line("BTN A 0")
            s_clear = wait_for_robot_condition(
                robot_log,
                timeout_s=8.0,
                predicate=lambda s: s.get("failsafe") == "0" and near_neutral(s, tol_us=70),
                pump_logs=[gamepad_log],
            )
            states["cleared"] = s_clear

            result = {
                "ok": bool(run_ok and return_ok),
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "drive_forward_axis": drive_forward_axis,
                "drive_hold_s": drive_hold_s,
                "drive_settle_s": float(drive_settle_s),
                "thresholds": {
                    "delta_a": float(drive_current_delta_a),
                    "min_current_a": float(drive_min_current_a),
                    "return_tol_a": float(drive_return_tol_a),
                },
                "baseline": {"median_a": baseline_med, "samples": len(baseline_values)},
                "drive_run": {"median_a": run_med, "delta_a": run_delta, "ok": run_ok, "samples": len(run_values)},
                "estop": {"tail_median_a": estop_tail, "ok": return_ok, "samples": len(estop_values)},
                "states": states,
            }

            (out_dir / "estop_drive_result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            (out_dir / "psu_current_samples.json").write_text(json.dumps(psu_samples, indent=2, sort_keys=True), encoding="utf-8")
            try:
                payload = labctl_psu_snapshot(psu_channel)
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
            (out_dir / "psu_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            if not result["ok"]:
                raise RuntimeError(f"estop while driving failed (result={result})")

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "estop while driving passed"


@step("Weapon Disarmed Guard Test")
def do_weapon_disarmed_guard(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    guard_axis: int,
    guard_hold_s: float,
    guard_baseline_s: float,
    guard_sample_interval_s: float,
    guard_max_delta_a: float,
    out_dir: Path | None = None,
) -> str:
    """
    Assert commanding weapon throttle while disarmed does not spin the motor.

    Signals checked:
    - Robot reports armed=0 and weapon=DISARMED.
    - PSU current does not rise above baseline by more than guard_max_delta_a.
    """
    if psu_channel is None:
        raise RuntimeError("psu_channel is required for weapon_disarmed_guard")

    if psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    # Power ESC supply.
    labctl_psu_set(psu_channel, psu_voltage, psu_current)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        psu_samples: list[dict] = []
        states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
            except Exception:
                pass
            if not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        def psu_sample_current(phase: str) -> float | None:
            value = labctl_psu_measure(psu_channel, "current")
            psu_samples.append(
                {
                    "t_s": round(time.monotonic() - suite_t0, 3),
                    "phase": phase,
                    "current_a": value,
                }
            )
            return value

        def drain_robot_serial(max_s: float) -> None:
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if not line:
                    break

        def sample_current_window(phase: str, duration_s: float, *, settle_s: float = 0.0) -> list[float]:
            values: list[float] = []
            duration_s = max(0.0, float(duration_s))
            settle_s = max(0.0, float(settle_s))
            start_t = time.monotonic()
            next_sample = start_t
            while True:
                now = time.monotonic()
                elapsed = now - start_t
                if elapsed >= duration_s:
                    break
                drain_robot_serial(0.02)
                if now < next_sample:
                    time.sleep(min(0.01, next_sample - now))
                    continue
                current = psu_sample_current(phase)
                if current is not None and elapsed >= settle_s:
                    values.append(current)
                next_sample += max(0.05, float(guard_sample_interval_s))
            return values

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("batt_mv") == "12500", pump_logs=[gamepad_log])

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            # Assert disarmed.
            s_dis = wait_for_robot_condition(
                robot_log,
                timeout_s=5.0,
                predicate=lambda s: s.get("failsafe") == "0" and s.get("armed") == "0" and s.get("weapon") == "DISARMED",
                pump_logs=[gamepad_log],
            )
            states["disarmed"] = s_dis

            # Baseline while disarmed and stopped.
            gamepad_log.send_line("AXIS RY 0")
            baseline_values = sample_current_window("baseline", guard_baseline_s, settle_s=0.0)
            baseline_med = statistics.median(baseline_values) if baseline_values else None
            if baseline_med is None:
                raise RuntimeError("no PSU current samples for baseline")

            # Command weapon while disarmed.
            guard_axis = max(-127, min(127, int(guard_axis)))
            if guard_axis < 0:
                guard_axis = 0
            guard_hold_s = max(0.4, float(guard_hold_s))

            gamepad_log.send_line(f"AXIS RY {guard_axis}")
            run_values = sample_current_window("disarmed_cmd", guard_hold_s, settle_s=0.2)
            run_med = statistics.median(run_values) if run_values else None

            # Stop.
            gamepad_log.send_line("AXIS RY 0")
            s_after = wait_for_robot_condition(
                robot_log,
                timeout_s=5.0,
                predicate=lambda s: s.get("armed") == "0" and s.get("weapon") == "DISARMED",
                pump_logs=[gamepad_log],
            )
            states["after_cmd"] = s_after

            if run_med is None:
                raise RuntimeError("no PSU current samples during disarmed command")
            delta = run_med - baseline_med
            ok = delta <= float(guard_max_delta_a)

            result = {
                "ok": bool(ok),
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "guard_axis": guard_axis,
                "guard_hold_s": guard_hold_s,
                "guard_baseline_s": float(guard_baseline_s),
                "thresholds": {"max_delta_a": float(guard_max_delta_a)},
                "baseline": {"median_a": baseline_med, "samples": len(baseline_values)},
                "run": {"median_a": run_med, "delta_a": delta, "samples": len(run_values)},
                "states": states,
            }

            (out_dir / "weapon_disarmed_guard_result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            (out_dir / "psu_current_samples.json").write_text(json.dumps(psu_samples, indent=2, sort_keys=True), encoding="utf-8")
            try:
                payload = labctl_psu_snapshot(psu_channel)
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
            (out_dir / "psu_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            if not ok:
                raise RuntimeError(f"weapon disarmed guard failed (delta={delta}A baseline={baseline_med}A run={run_med}A)")

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "weapon disarmed guard passed"


@step("E-Stop While Weapon Spinning Test")
def do_estop_weapon(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    spin_axis: int,
    spin_hold_s: float,
    spin_baseline_s: float,
    spin_sample_interval_s: float,
    spin_settle_s: float,
    spin_current_delta_a: float,
    spin_min_current_a: float,
    spin_return_tol_a: float,
    out_dir: Path | None = None,
) -> str:
    """
    Assert emergency stop works while the weapon is actively spinning.

    Signals checked:
    - PSU current rises during spin and drops near baseline after e-stop.
    - Robot reports failsafe=1 and weapon returns to DISARMED/speed=0.
    """
    if psu_channel is None:
        raise RuntimeError("psu_channel is required for estop_weapon")

    if psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    labctl_psu_set(psu_channel, psu_voltage, psu_current)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        psu_samples: list[dict] = []
        states: dict[str, dict[str, str]] = {}

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
            except Exception:
                pass
            if not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        def psu_sample_current(phase: str) -> float | None:
            value = labctl_psu_measure(psu_channel, "current")
            psu_samples.append(
                {
                    "t_s": round(time.monotonic() - suite_t0, 3),
                    "phase": phase,
                    "current_a": value,
                }
            )
            return value

        def drain_robot_serial(max_s: float) -> None:
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if not line:
                    break

        def sample_current_window(phase: str, duration_s: float, *, settle_s: float = 0.0) -> list[float]:
            values: list[float] = []
            duration_s = max(0.0, float(duration_s))
            settle_s = max(0.0, float(settle_s))
            start_t = time.monotonic()
            next_sample = start_t
            while True:
                now = time.monotonic()
                elapsed = now - start_t
                if elapsed >= duration_s:
                    break
                drain_robot_serial(0.02)
                if now < next_sample:
                    time.sleep(min(0.01, next_sample - now))
                    continue
                current = psu_sample_current(phase)
                if current is not None and elapsed >= settle_s:
                    values.append(current)
                next_sample += max(0.05, float(spin_sample_interval_s))
            return values

        def tail_median(values: list[float], n: int = 3) -> float | None:
            if not values:
                return None
            n = max(1, min(int(n), len(values)))
            return statistics.median(values[-n:])

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("batt_mv") == "12500", pump_logs=[gamepad_log])

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)
            # Allow the robot-side neutral-sticks guard (500ms) to clear before arming.
            time.sleep(0.7)

            wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("failsafe") == "0", pump_logs=[gamepad_log])

            # Arm.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            s_arm = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1", pump_logs=[gamepad_log])
            states["armed"] = s_arm

            # Wait for weapon state machine to finish arming (DShot setup can take a few seconds).
            wait_for_robot_condition(robot_log, timeout_s=20.0, predicate=lambda s: s.get("weapon") in ("ARMED", "SPINNING"), pump_logs=[gamepad_log])

            # Clamp + enforce unidirectional.
            spin_axis = max(-127, min(127, int(spin_axis)))
            if spin_axis < 0:
                spin_axis = 0
            spin_hold_s = max(0.8, float(spin_hold_s))

            gamepad_log.send_line("AXIS RY 0")
            time.sleep(0.2)

            baseline_values = sample_current_window("baseline", spin_baseline_s, settle_s=0.0)
            baseline_med = statistics.median(baseline_values) if baseline_values else None
            if baseline_med is None:
                raise RuntimeError("no PSU current samples for baseline")

            # Spin.
            gamepad_log.send_line(f"AXIS RY {spin_axis}")
            s_spin = wait_for_robot_condition(
                robot_log,
                timeout_s=6.0,
                predicate=lambda s: s.get("weapon") == "SPINNING" or (s.get("speed") and s.get("speed") != "0"),
                pump_logs=[gamepad_log],
            )
            states["spinning"] = s_spin

            run_values = sample_current_window("run", spin_hold_s, settle_s=spin_settle_s)
            run_med = statistics.median(run_values) if run_values else None
            if run_med is None:
                raise RuntimeError("no PSU current samples while spinning")
            delta = run_med - baseline_med
            run_ok = (delta >= float(spin_current_delta_a)) and (run_med >= float(spin_min_current_a))

            # Emergency stop while still commanding throttle.
            gamepad_log.send_line("BTN L1 1")
            gamepad_log.send_line("BTN R1 1")
            s_estop = wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("failsafe") == "1", pump_logs=[gamepad_log])
            states["estop"] = s_estop
            gamepad_log.send_line("BTN L1 0")
            gamepad_log.send_line("BTN R1 0")

            s_stop = wait_for_robot_condition(
                robot_log,
                timeout_s=6.0,
                predicate=lambda s: s.get("weapon") == "DISARMED" and s.get("speed") == "0",
                pump_logs=[gamepad_log],
            )
            states["stopped_after_estop"] = s_stop

            estop_values = sample_current_window("estop", 1.4, settle_s=0.2)
            estop_tail = tail_median(estop_values, n=3)
            return_ok = (estop_tail is not None) and (estop_tail <= (baseline_med + float(spin_return_tol_a)))

            # Clear emergency stop (hold A).
            gamepad_log.send_line("BTN A 1")
            time.sleep(2.3)
            gamepad_log.send_line("BTN A 0")
            s_clear = wait_for_robot_condition(
                robot_log,
                timeout_s=10.0,
                predicate=lambda s: s.get("failsafe") == "0" and s.get("armed") == "0" and s.get("weapon") == "DISARMED",
                pump_logs=[gamepad_log],
            )
            states["cleared"] = s_clear

            # Stop commanding.
            gamepad_log.send_line("AXIS RY 0")

            result = {
                "ok": bool(run_ok and return_ok),
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "spin_axis": spin_axis,
                "spin_hold_s": spin_hold_s,
                "spin_baseline_s": float(spin_baseline_s),
                "spin_settle_s": float(spin_settle_s),
                "thresholds": {
                    "delta_a": float(spin_current_delta_a),
                    "min_current_a": float(spin_min_current_a),
                    "return_tol_a": float(spin_return_tol_a),
                },
                "baseline": {"median_a": baseline_med, "samples": len(baseline_values)},
                "run": {"median_a": run_med, "delta_a": delta, "ok": run_ok, "samples": len(run_values)},
                "estop": {"tail_median_a": estop_tail, "ok": return_ok, "samples": len(estop_values)},
                "states": states,
            }

            (out_dir / "estop_weapon_result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            (out_dir / "psu_current_samples.json").write_text(json.dumps(psu_samples, indent=2, sort_keys=True), encoding="utf-8")
            try:
                payload = labctl_psu_snapshot(psu_channel)
            except Exception as exc:
                payload = {"ok": False, "error": str(exc)}
            (out_dir / "psu_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            if not result["ok"]:
                raise RuntimeError(f"estop while weapon spinning failed (result={result})")

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "estop while weapon spinning passed"


@step("Weapon Spin Test")
def do_weapon_spin(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    spin_axis: int,
    spin_hold_s: float,
    spin_baseline_s: float,
    spin_sample_interval_s: float,
    spin_settle_s: float,
    spin_current_delta_a: float,
    spin_min_current_a: float,
    require_telemetry: bool,
    telem_min_rpm: int,
    out_dir: Path | None = None,
) -> str:
    if psu_channel is not None and psu_off_first:
        labctl_psu_off(psu_channel)

    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start the suite from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    # Power ESC supply (best-effort; suite will still fail if motor never produces telemetry).
    if psu_channel is not None:
        try:
            labctl_psu_set(psu_channel, psu_voltage, psu_current)
        except Exception:
            pass

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        psu_samples: list[dict] = []
        weapon_armed = False

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
                # Only attempt to disarm if we armed during this suite. Avoids accidental arm at teardown.
                if weapon_armed:
                    gamepad_log.send_line("BTN B 1")
                    time.sleep(0.15)
                    gamepad_log.send_line("BTN B 0")
            except Exception:
                pass
            if psu_channel is not None and not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            # Put both devices into a deterministic state.
            gamepad_log.send_line("RESET")

            # Wait for at least one status sample so we know the HITL console tick is alive.
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)
            # Allow the robot-side neutral-sticks guard (500ms) to clear before arming.
            time.sleep(0.7)

            # Arm toggle with B.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1", pump_logs=[gamepad_log])
            weapon_armed = True

            # Wait for weapon state machine to finish arming (DShot setup can take a few seconds).
            wait_for_robot_condition(
                robot_log,
                timeout_s=20.0,
                predicate=lambda s: s.get("weapon") in ("ARMED", "SPINNING"),
                pump_logs=[gamepad_log],
            )

            # Spin at a safe low command for a short hold.
            spin_axis = max(-127, min(127, int(spin_axis)))
            if spin_axis < 0:
                spin_axis = 0
            spin_hold_s = max(0.0, float(spin_hold_s))

            # Establish baseline PSU current draw while armed and commanded stopped.
            gamepad_log.send_line("AXIS RY 0")
            time.sleep(0.2)

            telemetry_rpms: list[int] = []
            telemetry_ok = False

            def observe_robot_line(line: str) -> None:
                nonlocal telemetry_ok
                m = HITL_STATUS_RE.match(line)
                if not m:
                    return
                status = parse_kv_payload(m.group(1))
                if status.get("telem") != "1":
                    return
                rpm_s = status.get("rpm")
                if not rpm_s:
                    return
                try:
                    rpm = int(rpm_s)
                except ValueError:
                    return
                telemetry_rpms.append(rpm)
                if rpm >= int(telem_min_rpm):
                    telemetry_ok = True

            def drain_robot_serial(max_s: float) -> None:
                deadline = time.monotonic() + max_s
                while time.monotonic() < deadline:
                    line = robot_log.read_line()
                    if not line:
                        break
                    observe_robot_line(line)

            def psu_sample_current(phase: str) -> float | None:
                if psu_channel is None:
                    return None
                value = labctl_psu_measure(psu_channel, "current")
                psu_samples.append(
                    {
                        "t_s": round(time.monotonic() - suite_t0, 3),
                        "phase": phase,
                        "current_a": value,
                    }
                )
                return value

            def sample_current_window(phase: str, duration_s: float, *, settle_s: float = 0.0) -> list[float]:
                values: list[float] = []
                if psu_channel is None:
                    return values
                duration_s = max(0.0, float(duration_s))
                settle_s = max(0.0, float(settle_s))
                start_t = time.monotonic()
                next_sample = start_t
                while True:
                    now = time.monotonic()
                    elapsed = now - start_t
                    if elapsed >= duration_s:
                        break
                    drain_robot_serial(0.02)
                    if now < next_sample:
                        time.sleep(min(0.01, next_sample - now))
                        continue
                    current = psu_sample_current(phase)
                    if current is not None and elapsed >= settle_s:
                        values.append(current)
                    next_sample += max(0.05, float(spin_sample_interval_s))
                return values

            baseline_values = sample_current_window("baseline", spin_baseline_s, settle_s=0.0)
            baseline_med = statistics.median(baseline_values) if baseline_values else None

            # Start spin and sample during the entire hold (optionally skipping the first settle period).
            gamepad_log.send_line(f"AXIS RY {spin_axis}")
            run_values = sample_current_window("run", spin_hold_s, settle_s=spin_settle_s)
            run_med = statistics.median(run_values) if run_values else None

            # Determine pass/fail based on telemetry and/or PSU current delta.
            current_ok = False
            delta = None
            if baseline_med is not None and run_med is not None:
                delta = run_med - baseline_med
                if delta >= float(spin_current_delta_a) and run_med >= float(spin_min_current_a):
                    current_ok = True

            ok = telemetry_ok if require_telemetry else (telemetry_ok or current_ok)

            # Stop.
            gamepad_log.send_line("AXIS RY 0")
            wait_for_robot_condition(robot_log, timeout_s=10.0, predicate=lambda s: s.get("speed") == "0")

            # Disarm.
            time.sleep(0.2)  # Respect debounce timing in firmware.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("armed") == "0")
            weapon_armed = False

            # Explicit telemetry snapshot for the logs.
            robot_log.send_line("HITL TELEMSTATS")
            robot_log.send_line("HITL TELEM")
            time.sleep(0.5)
            for _ in range(50):
                robot_log.read_line()

            # PSU snapshot, if available (best-effort).
            if psu_channel is not None:
                try:
                    payload = labctl_psu_snapshot(psu_channel)
                except Exception as exc:
                    payload = {"ok": False, "error": str(exc)}
                (out_dir / "psu_snapshot.json").write_text(
                    json.dumps(payload, indent=2, sort_keys=True),
                    encoding="utf-8",
                )

            # Persist current sampling + computed result for debugging/plotting.
            (out_dir / "psu_current_samples.json").write_text(
                json.dumps(psu_samples, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            spin_result = {
                "ok": ok,
                "require_telemetry": require_telemetry,
                "spin_axis": spin_axis,
                "spin_hold_s": spin_hold_s,
                "spin_settle_s": float(spin_settle_s),
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage if psu_channel is not None else None,
                "psu_current_limit_set": psu_current if psu_channel is not None else None,
                "baseline": {
                    "duration_s": float(spin_baseline_s),
                    "samples": len(baseline_values),
                    "median_a": baseline_med,
                },
                "run": {
                    "duration_s": float(spin_hold_s),
                    "samples": len(run_values),
                    "median_a": run_med,
                },
                "thresholds": {
                    "delta_a": float(spin_current_delta_a),
                    "min_current_a": float(spin_min_current_a),
                },
                "delta_a": delta,
                "current_ok": current_ok,
                "telemetry_ok": telemetry_ok,
                "telemetry_rpms": {
                    "samples": len(telemetry_rpms),
                    "min": min(telemetry_rpms) if telemetry_rpms else None,
                    "median": (statistics.median(telemetry_rpms) if telemetry_rpms else None),
                    "max": max(telemetry_rpms) if telemetry_rpms else None,
                },
            }
            (out_dir / "weapon_spin_result.json").write_text(
                json.dumps(spin_result, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            if not ok:
                if require_telemetry:
                    raise RuntimeError(
                        "no valid DShot telemetry (rpm) observed while spinning "
                        f"(baseline_med={baseline_med}A run_med={run_med}A delta={delta}A)"
                    )
                raise RuntimeError(
                    "no spin signal detected (need telemetry rpm>0 or PSU current delta). "
                    f"(baseline_med={baseline_med}A run_med={run_med}A delta={delta}A)"
                )

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "weapon spin passed"


HITL_LATENCY_EVENT_RE = re.compile(r"^HITL LATENCY EVENT (\S+) (.+)$")
HITL_LATENCY_RESULT_RE = re.compile(r"^HITL LATENCY RESULT (.+)$")
HITL_LATENCY_DOWN_RE = re.compile(r"^HITL LATENCY DOWN (.+)$")
HITL_CMD_RE = re.compile(r"^HITL CMD (.+)$")
HITL_SENT_RE = re.compile(r"^HITL SENT (.+)$")


def _median_filter(values: list[float], window: int = 3) -> list[float]:
    """Apply a sliding-window median filter to a list of floats."""
    if window < 2 or len(values) <= window:
        return list(values)
    half = window // 2
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(float(statistics.median(values[lo:hi])))
    return out


def _generate_sine_axis_seq(n_cycles: int, axis_min: int, axis_max: int) -> list[int]:
    """Generate a sine-wave axis value sequence for latency test cycles.

    Returns a list of n_cycles positive axis values that trace a sine wave
    from axis_min up through axis_max and back down. This exercises the full
    ramp range and produces varied motor responses for better latency statistics.
    """
    import math
    if n_cycles <= 1:
        return [axis_max]
    values: list[int] = []
    for i in range(n_cycles):
        # Map cycle index to a half-sine: 0 -> pi.
        phase = math.pi * i / (n_cycles - 1)
        frac = math.sin(phase)
        v = round(axis_min + frac * (axis_max - axis_min))
        v = max(axis_min, min(axis_max, v))
        values.append(v)
    return values


@step("Weapon Latency Test")
def do_weapon_latency(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    spin_axis: int,
    spin_axis_seq: list[int] | None,
    latency_baseline_s: float,
    latency_hold_s: float,
    latency_cycles: int,
    latency_rpm_threshold: int,
    latency_telem_rate_ms: int,
    latency_status_rate_ms: int,
    check_drift: bool = False,
    max_drift_ms_per_cycle: float = 2.0,
    max_latency_ms: float = 300.0,
    out_dir: Path | None = None,
) -> str:
    """
    Precision latency measurement using firmware-side timestamps and RPM telemetry.

    Two-layer measurement:
    - Layer 1 (precise): Robot firmware time_us_64() timestamps internal events
      (gamepad RY change -> target set -> DShot sent -> RPM threshold crossed).
    - Layer 2 (approximate): Host time.monotonic() timestamps command send and
      response arrival (~5-10ms USB serial uncertainty).

    Emulator timestamps (HITL CMD / HITL SENT) measure emulator-internal delay.
    BT link latency estimated as: host_total - fw_internal - emulator_internal - USB_overhead.
    """
    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode so we always start from a known state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    # Power ESC supply if channel provided.
    if psu_channel is not None:
        if psu_off_first:
            labctl_psu_off(psu_channel)
        labctl_psu_set(psu_channel, psu_voltage, psu_current)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        weapon_armed = False

        # Optional PSU sampling (secondary data only, not used for latency calc).
        import threading
        psu_samples: list[dict] = []
        psu_samples_lock = threading.Lock()
        psu_stop = threading.Event()
        psu_thread: threading.Thread | None = None

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
                robot_log.send_line("HITL LATENCY DISARM")
                if weapon_armed:
                    time.sleep(0.2)
                    gamepad_log.send_line("BTN B 1")
                    time.sleep(0.30)
                    gamepad_log.send_line("BTN B 0")
            except Exception:
                pass
            if psu_channel is not None and not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        def psu_sampler_loop() -> None:
            if psu_channel is None:
                return
            while not psu_stop.is_set():
                t_before = time.monotonic()
                value = labctl_psu_measure(psu_channel, "current")
                t_after = time.monotonic()
                sample = {
                    "t_s": round(t_after - suite_t0, 3),
                    "t_mid_s": round((t_before + t_after) / 2.0 - suite_t0, 3),
                    "duration_s": round(t_after - t_before, 3),
                    "current_a": value,
                }
                with psu_samples_lock:
                    psu_samples.append(sample)
                time.sleep(0.05)

        # Collect time-series from STATUS lines and latency events from firmware.
        time_series: list[dict] = []
        fw_events: dict[str, object] = {}
        emu_events: dict[str, object] = {}
        fw_result_kv: dict[str, str] = {}
        fw_down_kv: dict[str, str] = {}

        def observe_line(line: str, source: str) -> None:
            """Parse both robot and emulator serial lines for latency data."""
            t_host = round(time.monotonic() - suite_t0, 6)

            if source == "robot":
                # STATUS lines -> time series.
                m = HITL_STATUS_RE.match(line)
                if m:
                    kv = parse_kv_payload(m.group(1))
                    try:
                        target = int(kv.get("target") or "0")
                    except ValueError:
                        target = 0
                    try:
                        speed = int(kv.get("speed") or "0")
                    except ValueError:
                        speed = 0
                    try:
                        thr = int(kv.get("thr") or "0")
                    except ValueError:
                        thr = 0
                    try:
                        rpm = int(kv.get("rpm") or "0")
                    except ValueError:
                        rpm = 0
                    time_series.append({
                        "t_s": t_host,
                        "target": target,
                        "speed": speed,
                        "thr": thr,
                        "rpm": rpm,
                    })
                    return

                # Latency events -> fw_events dict.
                m = HITL_LATENCY_EVENT_RE.match(line)
                if m:
                    event_name = m.group(1)
                    kv = parse_kv_payload(m.group(2))
                    key = f"host_robot_{event_name}_s"
                    if key not in fw_events:
                        fw_events[key] = t_host
                    t_us_str = kv.get("t_us")
                    if t_us_str:
                        try:
                            fw_events[f"fw_{event_name}_us"] = int(t_us_str)
                        except ValueError:
                            pass
                    return

                # Spinup result line.
                m = HITL_LATENCY_RESULT_RE.match(line)
                if m:
                    for token in m.group(1).strip().split():
                        if "=" in token:
                            k, v = token.split("=", 1)
                            fw_result_kv[k] = v
                    return

                # Spindown result line.
                m = HITL_LATENCY_DOWN_RE.match(line)
                if m:
                    for token in m.group(1).strip().split():
                        if "=" in token:
                            k, v = token.split("=", 1)
                            fw_down_kv[k] = v
                    return

            elif source == "emulator":
                m = HITL_CMD_RE.match(line)
                if m:
                    kv = parse_kv_payload(m.group(1))
                    t_ms = kv.get("t_ms")
                    if t_ms and "emu_cmd_ms" not in emu_events:
                        try:
                            emu_events["emu_cmd_ms"] = int(t_ms)
                        except ValueError:
                            pass
                    return

                m = HITL_SENT_RE.match(line)
                if m:
                    kv = parse_kv_payload(m.group(1))
                    t_ms = kv.get("t_ms")
                    # Only capture the first SENT after CMD was recorded
                    # (ignore the continuous stream of idle ry=0 reports).
                    if t_ms and "emu_cmd_ms" in emu_events and "emu_sent_ms" not in emu_events:
                        try:
                            emu_events["emu_sent_ms"] = int(t_ms)
                        except ValueError:
                            pass
                    if "emu_cmd_ms" in emu_events and "host_emu_hid_sent_s" not in emu_events:
                        emu_events["host_emu_hid_sent_s"] = t_host
                    return

        def drain_both(max_s: float = 0.02) -> None:
            """Drain both serial ports, parsing lines."""
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if line:
                    observe_line(line, "robot")
                line = gamepad_log.read_line()
                if line:
                    observe_line(line, "emulator")
                if not line:
                    time.sleep(0.001)

        def tight_poll(timeout_s: float, until_key: str | None = None) -> None:
            """Poll both serial ports at ~1ms until timeout or until a key appears in fw_events."""
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if line:
                    observe_line(line, "robot")
                line = gamepad_log.read_line()
                if line:
                    observe_line(line, "emulator")
                if until_key and until_key in fw_events:
                    return
                time.sleep(0.001)

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)
            wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("failsafe") == "0", pump_logs=[gamepad_log])

            # Configure fast telemetry decode and status rates AFTER BT
            # connection is established.  Setting these before ensure_robot_ready
            # floods the 64-byte USB CDC TX buffer, corrupting the BTADDR response.
            latency_telem_rate_ms = max(2, int(latency_telem_rate_ms))
            latency_status_rate_ms = max(5, int(latency_status_rate_ms))
            robot_log.send_line(f"HITL TELEMRATE {latency_telem_rate_ms}")
            time.sleep(0.05)
            robot_log.send_line(f"HITL STATUSRATE {latency_status_rate_ms}")
            time.sleep(0.1)
            # Allow the robot-side neutral-sticks guard (500ms) to clear before arming.
            time.sleep(0.7)

            # Arm.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1", pump_logs=[gamepad_log])
            weapon_armed = True

            # Wait for weapon to finish arming (DShot setup can take a few seconds).
            wait_for_robot_condition(
                robot_log,
                timeout_s=20.0,
                predicate=lambda s: s.get("weapon") in ("ARMED", "SPINNING"),
                pump_logs=[gamepad_log],
            )

            # Clamp + enforce unidirectional.
            spin_axis = max(0, min(127, int(spin_axis)))
            axis_seq: list[int] | None = None
            if spin_axis_seq:
                axis_seq = []
                for v in spin_axis_seq:
                    try:
                        iv = int(v)
                    except Exception:
                        continue
                    iv = max(0, min(127, iv))
                    axis_seq.append(iv)
                if not axis_seq:
                    axis_seq = None

            # Default: generate a sine-wave axis sequence for varied motor responses.
            if axis_seq is None:
                axis_seq = _generate_sine_axis_seq(
                    latency_cycles,
                    axis_min=max(20, spin_axis // 3),
                    axis_max=spin_axis,
                )

            latency_baseline_s = max(0.8, float(latency_baseline_s))
            latency_hold_s = max(1.0, float(latency_hold_s))
            latency_cycles = max(1, int(latency_cycles))
            latency_rpm_threshold = max(1, int(latency_rpm_threshold))

            cycles: list[dict] = []

            # Ensure the weapon is commanded stopped before starting.
            gamepad_log.send_line("AXIS RY 0")
            time.sleep(0.25)

            # Warm-up: right after boot/arm, some ESCs ignore the first few throttle
            # updates or telemetry can be "stuck" on stale values. Do a short spin-up
            # and stop before the measured cycles so the first measured cycle is stable.
            warm_axis = axis_seq[0] if axis_seq else spin_axis
            gamepad_log.send_line(f"AXIS RY {warm_axis}")
            deadline = time.monotonic() + min(1.5, max(0.8, latency_hold_s))
            while time.monotonic() < deadline:
                drain_both(0.02)
            gamepad_log.send_line("AXIS RY 0")
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                drain_both(0.02)
            # Ensure we're back to rest.
            wait_for_robot_condition(
                robot_log,
                timeout_s=12.0,
                predicate=lambda s: s.get("speed") == "0" and s.get("weapon") in ("ARMED", "SPINNING"),
                pump_logs=[gamepad_log],
            )

            # Start optional PSU background sampler for plot overlay.
            if psu_channel is not None:
                psu_thread = threading.Thread(target=psu_sampler_loop, name="psu_sampler", daemon=True)
                psu_thread.start()

            for cycle_num in range(1, latency_cycles + 1):
                axis = axis_seq[(cycle_num - 1) % len(axis_seq)]
                # Ensure we've come fully to rest before this cycle.
                wait_for_robot_condition(
                    robot_log,
                    timeout_s=10.0,
                    predicate=lambda s: s.get("speed") == "0" and s.get("weapon") in ("ARMED", "SPINNING"),
                    pump_logs=[gamepad_log],
                )

                # Reset per-cycle state.
                time_series.clear()
                fw_events.clear()
                emu_events.clear()
                fw_result_kv.clear()
                fw_down_kv.clear()

                # Baseline: collect STATUS time-series at rest.
                baseline_deadline = time.monotonic() + latency_baseline_s
                while time.monotonic() < baseline_deadline:
                    drain_both(0.02)

                # Arm the firmware latency tracker.
                robot_log.send_line(f"HITL LATENCY ARM {latency_rpm_threshold}")
                time.sleep(0.05)
                drain_both(0.02)

                # Step up: send AXIS RY command.
                t_host_cmd = time.monotonic()
                t_host_cmd_s = round(t_host_cmd - suite_t0, 6)
                gamepad_log.send_line(f"AXIS RY {axis}")

                # Tight-poll for firmware RESULT or timeout.
                tight_poll(timeout_s=10.0, until_key="fw_rpm_seen_us")

                # Hold for steady-state, continuing to collect time-series.
                hold_deadline = time.monotonic() + latency_hold_s
                while time.monotonic() < hold_deadline:
                    drain_both(0.02)

                # Step down: send AXIS RY 0.
                t_host_down = time.monotonic()
                t_host_down_s = round(t_host_down - suite_t0, 6)
                gamepad_log.send_line("AXIS RY 0")

                # Wait for spindown (DOWN line) or rpm=0 in STATUS, or timeout.
                down_deadline = time.monotonic() + 10.0
                while time.monotonic() < down_deadline:
                    line = robot_log.read_line()
                    if line:
                        observe_line(line, "robot")
                    line = gamepad_log.read_line()
                    if line:
                        observe_line(line, "emulator")
                    if fw_down_kv:
                        break
                    # Check STATUS for rpm=0.
                    if time_series and time_series[-1].get("rpm", 999) == 0 and time_series[-1].get("speed", 1) == 0:
                        break
                    time.sleep(0.001)

                # Cool-down.
                time.sleep(0.5)
                drain_both(0.1)

                # --- Build cycle result ---
                # Firmware timestamps.
                def _fw_us(key: str) -> int | None:
                    v = fw_events.get(key)
                    if v is None:
                        v = fw_result_kv.get(key.replace("fw_", "").replace("_us", "") + "_us")
                    if v is not None:
                        try:
                            return int(v)
                        except (TypeError, ValueError):
                            pass
                    return None

                fw_ry_us = _fw_us("fw_ry_nonzero_us")
                fw_target_us = _fw_us("fw_target_set_us")
                fw_dshot_us = _fw_us("fw_dshot_nonzero_us")
                fw_rpm_us = _fw_us("fw_rpm_seen_us")

                # Compute firmware-side deltas.
                def _delta_us(a: int | None, b: int | None) -> float | None:
                    if a is None or b is None:
                        return None
                    return round((b - a) / 1000.0, 3)

                fw_total_ms = _delta_us(fw_ry_us, fw_rpm_us)
                fw_ry_to_target_ms = _delta_us(fw_ry_us, fw_target_us)
                fw_target_to_dshot_ms = _delta_us(fw_target_us, fw_dshot_us)
                fw_dshot_to_rpm_ms = _delta_us(fw_dshot_us, fw_rpm_us)

                # Host-side timestamps.
                host_emu_sent_s = emu_events.get("host_emu_hid_sent_s")
                host_robot_ry_s = fw_events.get("host_robot_ry_nonzero_s")
                host_robot_rpm_s = fw_events.get("host_robot_rpm_seen_s")
                total_host_ms = None
                if host_robot_rpm_s is not None:
                    total_host_ms = round((float(host_robot_rpm_s) - t_host_cmd_s) * 1000.0, 1)

                # Emulator internal delay.
                emu_cmd_ms = emu_events.get("emu_cmd_ms")
                emu_sent_ms = emu_events.get("emu_sent_ms")
                emu_internal_ms = None
                if isinstance(emu_cmd_ms, (int, float)) and isinstance(emu_sent_ms, (int, float)):
                    emu_internal_ms = round(float(emu_sent_ms) - float(emu_cmd_ms), 1)

                # Approximate BT link: host_total - fw_total - emu_internal - USB overhead (~4ms est).
                bt_link_approx_ms = None
                if total_host_ms is not None and fw_total_ms is not None:
                    residual = total_host_ms - fw_total_ms
                    if emu_internal_ms is not None:
                        residual -= emu_internal_ms
                    residual -= 4.0  # Estimated USB serial overhead (both directions).
                    bt_link_approx_ms = round(max(0.0, residual), 1)

                # Median-filter RPM time series for cleaner plots.
                raw_rpms = [pt.get("rpm", 0) for pt in time_series]
                filtered_rpms = _median_filter([float(r) for r in raw_rpms], window=3)
                for i, pt in enumerate(time_series):
                    if i < len(filtered_rpms):
                        pt["rpm_filtered"] = int(round(filtered_rpms[i]))

                cycle_result = {
                    "cycle": cycle_num,
                    "axis_value": axis,
                    "rpm_threshold": latency_rpm_threshold,
                    "timestamps": {
                        "host_cmd_sent_s": t_host_cmd_s,
                        "host_emu_hid_sent_s": host_emu_sent_s,
                        "host_robot_ry_event_s": host_robot_ry_s,
                        "host_robot_rpm_event_s": host_robot_rpm_s,
                        "host_cmd_down_s": t_host_down_s,
                        "fw_ry_us": fw_ry_us,
                        "fw_target_us": fw_target_us,
                        "fw_dshot_us": fw_dshot_us,
                        "fw_rpm_us": fw_rpm_us,
                        "emu_cmd_ms": emu_cmd_ms,
                        "emu_sent_ms": emu_sent_ms,
                    },
                    "latency_ms": {
                        "total_host": total_host_ms,
                        "total_fw": fw_total_ms,
                        "emu_internal": emu_internal_ms,
                        "bt_link_approx": bt_link_approx_ms,
                        "fw_input_to_target": fw_ry_to_target_ms,
                        "fw_target_to_dshot": fw_target_to_dshot_ms,
                        "fw_dshot_to_rpm": fw_dshot_to_rpm_ms,
                    },
                    "spindown": {
                        "host_cmd_down_s": t_host_down_s,
                        "fw_ry_zero_us": fw_down_kv.get("ry_us"),
                        "fw_rpm_below_us": fw_down_kv.get("rpm_us"),
                        "fw_total_down_us": fw_down_kv.get("total_us"),
                    },
                    "time_series": list(time_series),
                }
                cycles.append(cycle_result)

            # Stop + disarm.
            gamepad_log.send_line("AXIS RY 0")
            robot_log.send_line("HITL LATENCY DISARM")
            wait_for_robot_condition(
                robot_log,
                timeout_s=12.0,
                predicate=lambda s: s.get("speed") == "0" and s.get("target") == "0",
                pump_logs=[gamepad_log],
            )
            time.sleep(0.25)
            for attempt in range(2):
                gamepad_log.send_line("BTN B 1")
                time.sleep(0.20)
                gamepad_log.send_line("BTN B 0")
                try:
                    wait_for_robot_condition(robot_log, timeout_s=6.0, predicate=lambda s: s.get("armed") == "0")
                    break
                except RuntimeError:
                    if attempt == 1:
                        raise
                    time.sleep(0.25)
            weapon_armed = False

            # Snapshot telemetry debug for extra context.
            robot_log.send_line("HITL TELEMSTATS")
            time.sleep(0.2)
            for _ in range(30):
                robot_log.read_line()

            # Stop PSU sampling.
            psu_stop.set()
            if psu_thread is not None:
                psu_thread.join(timeout=3.0)

            # Persist PSU samples if available.
            with psu_samples_lock:
                psu_snapshot = list(psu_samples)
            if psu_snapshot:
                (out_dir / "psu_current_samples.json").write_text(
                    json.dumps(psu_snapshot, indent=2, sort_keys=True), encoding="utf-8")
            if psu_channel is not None:
                try:
                    payload = labctl_psu_snapshot(psu_channel)
                except Exception as exc:
                    payload = {"ok": False, "error": str(exc)}
                (out_dir / "psu_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

            # --- Build summary ---
            def summarize(values: list[float]) -> dict | None:
                if not values:
                    return None
                return {
                    "min": round(min(values), 3),
                    "median": round(statistics.median(values), 3),
                    "mean": round(statistics.mean(values), 3),
                    "max": round(max(values), 3),
                    "stddev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
                    "samples": len(values),
                }

            total_host_vals = [c["latency_ms"]["total_host"] for c in cycles if c["latency_ms"]["total_host"] is not None]
            total_fw_vals = [c["latency_ms"]["total_fw"] for c in cycles if c["latency_ms"]["total_fw"] is not None]
            bt_vals = [c["latency_ms"]["bt_link_approx"] for c in cycles if c["latency_ms"]["bt_link_approx"] is not None]
            ramp_vals = [c["latency_ms"]["fw_target_to_dshot"] for c in cycles if c["latency_ms"]["fw_target_to_dshot"] is not None]
            motor_vals = [c["latency_ms"]["fw_dshot_to_rpm"] for c in cycles if c["latency_ms"]["fw_dshot_to_rpm"] is not None]

            def cycle_ok(c: dict) -> bool:
                lat = c.get("latency_ms") or {}
                return lat.get("total_fw") is not None and lat.get("fw_dshot_to_rpm") is not None

            ok = all(cycle_ok(c) for c in cycles)

            # --- Drift analysis ---
            drift_info: dict[str, object] = {
                "check_drift": check_drift,
                "max_drift_ms_per_cycle": max_drift_ms_per_cycle,
                "max_latency_ms": max_latency_ms,
            }
            drift_fail_reasons: list[str] = []
            if len(total_fw_vals) >= 2:
                n = len(total_fw_vals)
                xs = list(range(n))
                ys = total_fw_vals

                # Linear regression: slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
                sum_x = sum(xs)
                sum_y = sum(ys)
                sum_xy = sum(x * y for x, y in zip(xs, ys))
                sum_x2 = sum(x * x for x in xs)
                denom = n * sum_x2 - sum_x * sum_x
                slope = (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0

                # Half-split comparison
                mid = n // 2
                first_half_mean = statistics.mean(ys[:mid])
                second_half_mean = statistics.mean(ys[mid:])

                max_val = max(ys)

                drift_info.update({
                    "slope_ms_per_cycle": round(slope, 4),
                    "first_half_mean_ms": round(first_half_mean, 3),
                    "second_half_mean_ms": round(second_half_mean, 3),
                    "half_delta_ms": round(second_half_mean - first_half_mean, 3),
                    "max_cycle_ms": round(max_val, 3),
                })

                if check_drift:
                    if slope > max_drift_ms_per_cycle:
                        drift_fail_reasons.append(
                            f"drift slope {slope:.4f} ms/cycle exceeds limit {max_drift_ms_per_cycle}")
                    if max_val > max_latency_ms:
                        drift_fail_reasons.append(
                            f"max cycle latency {max_val:.3f} ms exceeds limit {max_latency_ms}")

            if drift_fail_reasons:
                drift_info["drift_ok"] = False
                drift_info["drift_fail_reasons"] = drift_fail_reasons
                ok = False
            else:
                drift_info["drift_ok"] = True

            result = {
                "ok": bool(ok),
                "version": 2,
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "spin_axis": spin_axis,
                "spin_axis_seq": [c["axis_value"] for c in cycles],
                "rpm_threshold": latency_rpm_threshold,
                "telem_rate_ms": latency_telem_rate_ms,
                "status_rate_ms": latency_status_rate_ms,
                "latency_cycles": latency_cycles,
                "cycles": cycles,
                "summary": {
                    "total_host_ms": summarize(total_host_vals),
                    "total_fw_ms": summarize(total_fw_vals),
                    "bt_link_approx_ms": summarize(bt_vals),
                    "fw_ramp_ms": summarize(ramp_vals),
                    "fw_motor_telem_ms": summarize(motor_vals),
                    "cycles_with_fw_result": len(total_fw_vals),
                    "cycles_total": len(cycles),
                },
                "drift": drift_info,
            }
            (out_dir / "weapon_latency_result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

            if not result["ok"]:
                fail_parts = [f"summary={json.dumps(result.get('summary'), indent=2)}"]
                if drift_fail_reasons:
                    fail_parts.append(f"drift={drift_fail_reasons}")
                raise RuntimeError(f"weapon latency capture failed ({', '.join(fail_parts)})")

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "weapon latency passed"


@step("Weapon Zero Cross Test")
def do_weapon_zero_cross(
    repo_root: Path,
    psu_channel: int | None,
    psu_voltage: float,
    psu_current: float,
    psu_off_first: bool,
    leave_psu_on: bool,
    zero_cross_axis: int,
    zero_cross_hold_s: float,
    zero_cross_max_ms: float,
    zero_cross_cycles: int,
    out_dir: Path | None = None,
) -> str:
    """
    Validate smooth weapon direction reversal (zero-crossing).

    Spins the weapon forward, commands reverse, and measures how long the
    reversal takes.  Also detects the "never spins" bug (motor stuck at
    zero speed after direction change).
    """
    robot_port = resolve_robot_port()
    gamepad_port = resolve_gamepad_port()

    # Reboot both devices into application mode for a known start state.
    robot_usb_ser = get_usb_serial_for_tty(robot_port)
    gamepad_usb_ser = get_usb_serial_for_tty(gamepad_port)
    picotool_reboot_application(robot_usb_ser)
    wait_for_tty_reenumerate(robot_port, 15)
    picotool_reboot_application(gamepad_usb_ser)
    wait_for_tty_reenumerate(gamepad_port, 15)

    # Power ESC supply if channel provided.
    if psu_channel is not None:
        if psu_off_first:
            labctl_psu_off(psu_channel)
        labctl_psu_set(psu_channel, psu_voltage, psu_current)

    with serial.Serial(robot_port, 115200, timeout=0.05, write_timeout=1.0) as robot_ser, \
            serial.Serial(gamepad_port, 115200, timeout=0.05, write_timeout=1.0) as gamepad_ser:
        if out_dir is None:
            out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")
        suite_t0 = time.monotonic()
        weapon_armed = False

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
                if weapon_armed:
                    time.sleep(0.2)
                    gamepad_log.send_line("BTN B 1")
                    time.sleep(0.30)
                    gamepad_log.send_line("BTN B 0")
            except Exception:
                pass
            if psu_channel is not None and not leave_psu_on:
                try:
                    labctl_psu_off(psu_channel)
                except Exception:
                    pass

        # Time-series from STATUS lines.
        time_series: list[dict] = []

        def observe_robot_line(line: str) -> None:
            t_host = round(time.monotonic() - suite_t0, 6)
            m = HITL_STATUS_RE.match(line)
            if not m:
                return
            kv = parse_kv_payload(m.group(1))
            try:
                speed = int(kv.get("speed") or "0")
            except ValueError:
                speed = 0
            try:
                target = int(kv.get("target") or "0")
            except ValueError:
                target = 0
            weapon_state = kv.get("weapon", "")
            time_series.append({
                "t_s": t_host,
                "speed": speed,
                "target": target,
                "weapon": weapon_state,
            })

        def drain_both(max_s: float = 0.02) -> None:
            deadline = time.monotonic() + max_s
            while time.monotonic() < deadline:
                line = robot_log.read_line()
                if line:
                    observe_robot_line(line)
                line = gamepad_log.read_line()
                if not line:
                    time.sleep(0.001)

        try:
            # Drain startup noise.
            start = time.monotonic()
            while time.monotonic() - start < 3.0:
                robot_log.read_line()
                gamepad_log.read_line()

            gamepad_log.send_line("RESET")
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s, pump_logs=[gamepad_log])

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
                pump_logs=[gamepad_log],
            )

            ensure_robot_ready(robot_log, gamepad_log, timeout_s=40.0)

            # Configure fast status reporting for responsive speed tracking.
            robot_log.send_line("HITL STATUSRATE 10")
            time.sleep(0.1)

            # Allow the robot-side neutral-sticks guard (500ms) to clear.
            time.sleep(0.7)

            # Arm weapon.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1", pump_logs=[gamepad_log])
            weapon_armed = True

            # Wait for weapon state machine to finish arming.
            wait_for_robot_condition(
                robot_log,
                timeout_s=20.0,
                predicate=lambda s: s.get("weapon") in ("ARMED", "SPINNING"),
                pump_logs=[gamepad_log],
            )

            axis = max(1, min(127, int(zero_cross_axis)))
            zero_cross_hold_s = max(1.0, float(zero_cross_hold_s))
            zero_cross_max_ms = max(100.0, float(zero_cross_max_ms))
            zero_cross_cycles = max(1, int(zero_cross_cycles))

            cycles: list[dict] = []

            # Warm-up spin: ensures ESC is responding before measured cycles.
            gamepad_log.send_line(f"AXIS RY {axis}")
            deadline = time.monotonic() + min(2.0, zero_cross_hold_s)
            while time.monotonic() < deadline:
                drain_both(0.02)
            gamepad_log.send_line("AXIS RY 0")
            wait_for_robot_condition(
                robot_log,
                timeout_s=12.0,
                predicate=lambda s: s.get("speed") == "0" and s.get("weapon") in ("ARMED", "SPINNING"),
                pump_logs=[gamepad_log],
            )
            time.sleep(0.5)

            for cycle_num in range(1, zero_cross_cycles + 1):
                # Each cycle: forward → reverse → forward (a full round-trip).
                cycle_reversals: list[dict] = []

                for reversal_idx, (from_axis, to_axis) in enumerate([
                    (axis, -axis),
                    (-axis, axis),
                ]):
                    if reversal_idx == 0:
                        # First reversal: start from rest, spin up to from_axis.
                        wait_for_robot_condition(
                            robot_log,
                            timeout_s=12.0,
                            predicate=lambda s: s.get("speed") == "0" and s.get("weapon") in ("ARMED", "SPINNING"),
                            pump_logs=[gamepad_log],
                        )

                        time_series.clear()
                        gamepad_log.send_line(f"AXIS RY {from_axis}")

                        expected_sign = 1 if from_axis > 0 else -1
                        try:
                            wait_for_robot_condition(
                                robot_log,
                                timeout_s=15.0,
                                predicate=lambda s: (
                                    s.get("weapon") == "SPINNING" and
                                    _parse_int(s.get("speed")) is not None and
                                    abs(_parse_int(s.get("speed"))) > 0 and
                                    (_parse_int(s.get("speed")) > 0) == (expected_sign > 0)
                                ),
                                pump_logs=[gamepad_log],
                            )
                        except RuntimeError:
                            raise RuntimeError(
                                f"cycle {cycle_num} reversal {reversal_idx}: motor never reached "
                                f"from_axis={from_axis} direction (stuck-at-zero / never-spins bug?)"
                            )

                        # Hold at the initial speed.
                        hold_deadline = time.monotonic() + zero_cross_hold_s
                        while time.monotonic() < hold_deadline:
                            drain_both(0.02)
                    else:
                        # Subsequent reversals: motor is already spinning in from_axis
                        # direction from the previous reversal's hold phase. Just hold
                        # a bit longer to confirm stable spin before reversing again.
                        hold_deadline = time.monotonic() + zero_cross_hold_s
                        while time.monotonic() < hold_deadline:
                            drain_both(0.02)

                    # Command reversal and measure time.
                    time_series.clear()
                    t0 = time.monotonic()
                    t0_rel = round(t0 - suite_t0, 6)
                    gamepad_log.send_line(f"AXIS RY {to_axis}")

                    # Poll until speed crosses into the target direction or timeout.
                    target_sign = 1 if to_axis > 0 else -1
                    t_reversal_s = None
                    stuck_at_zero = False
                    reversal_deadline = t0 + max(zero_cross_max_ms / 1000.0 * 3, 5.0)
                    last_nonzero_t = t0  # Track if speed stays stuck at zero.
                    while time.monotonic() < reversal_deadline:
                        line = robot_log.read_line()
                        if line:
                            observe_robot_line(line)
                        line = gamepad_log.read_line()

                        # Check latest time_series entry.
                        if time_series:
                            latest_speed = time_series[-1]["speed"]
                            if latest_speed != 0:
                                last_nonzero_t = time.monotonic()
                            if (target_sign > 0 and latest_speed > 0) or \
                               (target_sign < 0 and latest_speed < 0):
                                t_reversal_s = time.monotonic() - t0
                                break

                        # Detect stuck-at-zero: speed has been 0 for >2s after the command.
                        if (time.monotonic() - t0) > 2.0 and (time.monotonic() - last_nonzero_t) > 2.0:
                            stuck_at_zero = True
                            break

                        time.sleep(0.001)

                    t_reversal_ms = round(t_reversal_s * 1000.0, 1) if t_reversal_s is not None else None

                    # Continue holding in the reversed direction to confirm stable spin.
                    if t_reversal_s is not None:
                        stable_deadline = time.monotonic() + min(1.0, zero_cross_hold_s)
                        while time.monotonic() < stable_deadline:
                            drain_both(0.02)

                    reversal_data = {
                        "from_axis": from_axis,
                        "to_axis": to_axis,
                        "t0_s": t0_rel,
                        "reversal_ms": t_reversal_ms,
                        "stuck_at_zero": stuck_at_zero,
                        "passed": (
                            t_reversal_ms is not None and
                            t_reversal_ms <= zero_cross_max_ms and
                            not stuck_at_zero
                        ),
                        "time_series": list(time_series),
                    }
                    cycle_reversals.append(reversal_data)

                    if stuck_at_zero:
                        # Motor stuck — try to recover for next reversal.
                        gamepad_log.send_line("AXIS RY 0")
                        time.sleep(1.0)
                        drain_both(0.1)

                # Stop between cycles.
                gamepad_log.send_line("AXIS RY 0")
                wait_for_robot_condition(
                    robot_log,
                    timeout_s=12.0,
                    predicate=lambda s: s.get("speed") == "0",
                    pump_logs=[gamepad_log],
                )
                time.sleep(0.5)

                cycle_ok = all(r["passed"] for r in cycle_reversals)
                cycles.append({
                    "cycle": cycle_num,
                    "ok": cycle_ok,
                    "reversals": cycle_reversals,
                })

            # Disarm.
            gamepad_log.send_line("AXIS RY 0")
            time.sleep(0.25)
            for attempt in range(2):
                gamepad_log.send_line("BTN B 1")
                time.sleep(0.20)
                gamepad_log.send_line("BTN B 0")
                try:
                    wait_for_robot_condition(robot_log, timeout_s=6.0, predicate=lambda s: s.get("armed") == "0")
                    break
                except RuntimeError:
                    if attempt == 1:
                        raise
                    time.sleep(0.25)
            weapon_armed = False

            # Build result.
            all_reversal_ms = [
                r["reversal_ms"]
                for c in cycles for r in c["reversals"]
                if r["reversal_ms"] is not None
            ]
            any_stuck = any(
                r["stuck_at_zero"]
                for c in cycles for r in c["reversals"]
            )
            ok = all(c["ok"] for c in cycles)

            def summarize(values: list[float]) -> dict | None:
                if not values:
                    return None
                return {
                    "min": round(min(values), 1),
                    "median": round(statistics.median(values), 1),
                    "mean": round(statistics.mean(values), 1),
                    "max": round(max(values), 1),
                    "stddev": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
                    "samples": len(values),
                }

            result = {
                "ok": bool(ok),
                "zero_cross_axis": axis,
                "zero_cross_hold_s": zero_cross_hold_s,
                "zero_cross_max_ms": zero_cross_max_ms,
                "zero_cross_cycles": zero_cross_cycles,
                "psu_channel": psu_channel,
                "psu_voltage_set": psu_voltage,
                "psu_current_limit_set": psu_current,
                "any_stuck_at_zero": any_stuck,
                "reversal_ms": summarize(all_reversal_ms),
                "cycles": cycles,
            }
            (out_dir / "weapon_zero_cross_result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )

            if not ok:
                fail_parts: list[str] = []
                if any_stuck:
                    fail_parts.append("motor stuck at zero (never-spins bug)")
                for c in cycles:
                    for r in c["reversals"]:
                        if not r["passed"] and not r["stuck_at_zero"]:
                            fail_parts.append(
                                f"cycle {c['cycle']} {r['from_axis']}->{r['to_axis']}: "
                                f"{r['reversal_ms']}ms > {zero_cross_max_ms}ms limit"
                            )
                raise RuntimeError(
                    f"weapon zero-cross test failed: {'; '.join(fail_parts) or 'unknown'}"
                )

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "weapon zero-cross passed"


def _parse_int(val: str | None) -> int | None:
    """Parse an optional string to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="ThumbsUp HITL orchestrator")
    parser.add_argument("--no-build", action="store_true", help="skip firmware builds")
    parser.add_argument("--no-flash", action="store_true", help="skip flashing")
    parser.add_argument("--no-report", action="store_true", help="skip generating report.md/report.pdf")
    parser.add_argument("--run-dir", help="override output directory under hitl_logs/")
    parser.add_argument("--no-psu-off", action="store_true", help="do not force PSU off at start")
    parser.add_argument(
        "--psu-channel",
        type=int,
        default=1,
        help="PSU channel for weapon ESC (Rigol DP832). Use --psu-drive-channel for drive tests.",
    )
    parser.add_argument(
        "--psu-drive-channel",
        type=int,
        default=1,
        help="PSU channel for drive ESC (Rigol DP832). Default assumes all motors are on CH1.",
    )
    parser.add_argument("--psu-voltage", type=float, default=12.6, help="PSU voltage for active motor tests")
    parser.add_argument("--psu-current", type=float, default=5.0, help="PSU current limit for active motor tests")
    parser.add_argument("--leave-psu-on", action="store_true", help="leave PSU output enabled after suite")
    parser.add_argument("--spin-axis", type=int, default=60, help="Weapon spin command (RY axis -127..127)")
    parser.add_argument(
        "--spin-axis-seq",
        help="Optional comma-separated list of spin axis values to cycle per latency cycle (e.g. 20,40,60,80).",
    )
    parser.add_argument("--spin-hold-s", type=float, default=5.0, help="Seconds to hold weapon command")
    parser.add_argument("--spin-baseline-s", type=float, default=2.0, help="Seconds to sample baseline current before spin")
    parser.add_argument("--spin-sample-interval-s", type=float, default=0.2, help="PSU current sample interval (s)")
    parser.add_argument("--spin-settle-s", type=float, default=0.4, help="Seconds after spin start to ignore for current stats")
    parser.add_argument("--spin-current-delta-a", type=float, default=0.15, help="Min median current delta to treat as spinning")
    parser.add_argument("--spin-min-current-a", type=float, default=0.25, help="Min median current during run to treat as spinning")
    parser.add_argument("--spin-return-tol-a", type=float, default=0.10, help="Max median current above baseline after weapon stop/e-stop")
    parser.add_argument("--require-telemetry", action="store_true", help="Fail unless DShot telemetry rpm>0 is observed")
    parser.add_argument(
        "--telem-min-rpm",
        type=int,
        default=1000,
        help="Minimum RPM to treat as 'spinning' when using telemetry-based checks (filters idle/garbage RPM).",
    )
    parser.add_argument("--guard-axis", type=int, default=80, help="Weapon guard command (RY axis -127..127) while disarmed")
    parser.add_argument("--guard-hold-s", type=float, default=1.5, help="Seconds to hold disarmed weapon command")
    parser.add_argument("--guard-baseline-s", type=float, default=1.5, help="Seconds to sample baseline current before disarmed command")
    parser.add_argument("--guard-sample-interval-s", type=float, default=0.2, help="PSU current sample interval during guard test (s)")
    parser.add_argument("--guard-max-delta-a", type=float, default=0.08, help="Max allowed median current delta during disarmed command")
    parser.add_argument("--latency-baseline-s", type=float, default=1.5, help="Seconds to collect baseline time-series before each cycle")
    parser.add_argument("--latency-hold-s", type=float, default=2.0, help="Seconds to hold throttle command for steady-state after RPM seen")
    parser.add_argument("--latency-cycles", type=int, default=5, help="Number of step cycles to measure (uses sine-wave axis by default)")
    parser.add_argument("--latency-rpm-threshold", type=int, default=500, help="RPM threshold for latency crossing detection")
    parser.add_argument("--latency-telem-rate-ms", type=int, default=2, help="Weapon telemetry decode interval during latency test (ms)")
    parser.add_argument("--latency-status-rate-ms", type=int, default=10, help="Robot HITL STATUS interval during latency test (ms)")
    parser.add_argument("--soak-cycles", type=int, default=20, help="Number of cycles for latency soak test")
    parser.add_argument("--soak-axis", type=int, default=60, help="Fixed axis value for latency soak test")
    parser.add_argument("--soak-baseline-s", type=float, default=0.8, help="Baseline seconds per cycle for soak test")
    parser.add_argument("--soak-hold-s", type=float, default=1.5, help="Hold seconds per cycle for soak test")
    parser.add_argument("--soak-max-drift-ms", type=float, default=2.0, help="Max acceptable drift slope (ms/cycle) for soak test")
    parser.add_argument("--soak-max-latency-ms", type=float, default=300.0, help="Max acceptable single-cycle latency (ms) for soak test")
    parser.add_argument("--zero-cross-axis", type=int, default=100, help="Weapon zero-cross command magnitude (RY axis 1..127, mapped to ±axis)")
    parser.add_argument("--zero-cross-hold-s", type=float, default=3.0, help="Seconds to hold each direction before reversal")
    parser.add_argument("--zero-cross-max-ms", type=float, default=1000.0, help="Max allowed reversal time (ms), ~690ms expected with prime sequence")
    parser.add_argument("--zero-cross-cycles", type=int, default=2, help="Number of full round-trip reversal cycles")
    parser.add_argument("--drive-forward-axis", type=int, default=-80, help="Drive forward command (LY axis -127..127)")
    parser.add_argument("--drive-turn-axis", type=int, default=80, help="Drive turn command (LX axis -127..127)")
    parser.add_argument("--drive-hold-s", type=float, default=0.6, help="Seconds to hold each drive command")
    parser.add_argument("--drive-min-delta-us", type=int, default=60, help="Min PWM pulse delta from neutral to treat as moving")
    parser.add_argument("--drive-spin-hold-s", type=float, default=2.0, help="Seconds to hold each active drive command")
    parser.add_argument("--drive-spin-sample-interval-s", type=float, default=0.2, help="PSU current sample interval during drive tests (s)")
    parser.add_argument("--drive-spin-settle-s", type=float, default=0.3, help="Seconds after drive start to ignore for current stats")
    parser.add_argument("--drive-spin-current-delta-a", type=float, default=0.08, help="Min median current delta to treat as drive spinning")
    parser.add_argument("--drive-spin-min-current-a", type=float, default=0.10, help="Min median current during run to treat as drive spinning")
    parser.add_argument("--drive-spin-return-tol-a", type=float, default=0.08, help="Max median current deviation from baseline when stopped")
    parser.add_argument(
        "--suite",
        choices=[
            "smoke",
            "weapon_spin",
            "weapon_latency",
            "latency_soak",
            "weapon_disarmed_guard",
            "estop_weapon",
            "weapon_zero_cross",
            "drive_e2e",
            "disconnect_failsafe",
            "drive_spin",
            "estop_drive",
            "safety_active",
            "full_e2e",
        ],
        default="smoke",
    )
    args = parser.parse_args()
    spin_axis_seq = None
    if args.spin_axis_seq:
        parts = [p.strip() for p in re.split(r"[,\s]+", str(args.spin_axis_seq).strip()) if p.strip()]
        seq: list[int] = []
        for p in parts:
            try:
                seq.append(int(p, 0))
            except ValueError:
                raise SystemExit(f"invalid --spin-axis-seq value: {p!r}")
        spin_axis_seq = seq

    repo_root = Path(__file__).resolve().parents[1]

    run_started_at = now_iso()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
    else:
        run_dir = repo_root / "hitl_logs" / f"run_{run_id}_{args.suite}"
    steps_root = run_dir / "steps"
    steps_root.mkdir(parents=True, exist_ok=True)

    step_idx = 1

    def alloc_step_dir(step_name: str) -> Path:
        nonlocal step_idx
        d = steps_root / f"{step_idx:02d}_{slugify(step_name)}"
        step_idx += 1
        return d

    results: list[StepResult] = []
    exit_code = 0

    # Snapshot repo + hardware metadata (best-effort).
    git_meta: dict[str, object] = {}
    try:
        git_meta["commit"] = run_cmd(["git", "rev-parse", "HEAD"], cwd=str(repo_root)).stdout.strip()
        git_meta["branch"] = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo_root)).stdout.strip()
        git_meta["dirty"] = bool((run_cmd(["git", "status", "--porcelain=v1"], cwd=str(repo_root)).stdout or "").strip())
    except Exception as exc:
        git_meta = {"error": str(exc)}

    device_meta: dict[str, object] = {}
    try:
        robot_port = resolve_robot_port(timeout_s=1.0)
        device_meta["robot_port"] = robot_port
        device_meta["robot_usb_serial"] = get_usb_serial_for_tty(robot_port)
    except Exception:
        pass
    try:
        gamepad_port = resolve_gamepad_port(timeout_s=1.0)
        device_meta["gamepad_port"] = gamepad_port
        device_meta["gamepad_usb_serial"] = get_usb_serial_for_tty(gamepad_port)
    except Exception:
        pass

    psu_meta: dict[str, object] = {}
    try:
        psu_meta = json.loads(run_cmd(["labctl", "--json", "psu", "idn"], check=True, capture_output=True).stdout or "{}")
    except Exception:
        pass

    if not args.no_build:
        results.append(
            do_build(
                repo_root,
                build_robot_fw=True,
                build_gamepad_fw=True,
                out_dir=alloc_step_dir("Build Firmware"),
            )
        )
        if not results[-1].ok:
            exit_code = 1

    if not args.no_flash and exit_code == 0:
        results.append(
            do_flash(
                repo_root,
                flash_robot=True,
                flash_gamepad=True,
                out_dir=alloc_step_dir("Flash Firmware"),
            )
        )
        if not results[-1].ok:
            exit_code = 1

    # Don't attempt to run active tests if build/flash already failed.
    if exit_code == 0:
        if args.suite == "smoke":
            results.append(
                do_smoke(
                    repo_root,
                    args.psu_channel,
                    psu_off_first=not args.no_psu_off,
                    out_dir=alloc_step_dir("Smoke Test"),
                )
            )
        elif args.suite == "weapon_disarmed_guard":
            results.append(
                do_weapon_disarmed_guard(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    guard_axis=args.guard_axis,
                    guard_hold_s=args.guard_hold_s,
                    guard_baseline_s=args.guard_baseline_s,
                    guard_sample_interval_s=args.guard_sample_interval_s,
                    guard_max_delta_a=args.guard_max_delta_a,
                    out_dir=alloc_step_dir("Weapon Disarmed Guard Test"),
                )
            )
        elif args.suite == "estop_weapon":
            results.append(
                do_estop_weapon(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    spin_axis=args.spin_axis,
                    spin_hold_s=args.spin_hold_s,
                    spin_baseline_s=args.spin_baseline_s,
                    spin_sample_interval_s=args.spin_sample_interval_s,
                    spin_settle_s=args.spin_settle_s,
                    spin_current_delta_a=args.spin_current_delta_a,
                    spin_min_current_a=args.spin_min_current_a,
                    spin_return_tol_a=args.spin_return_tol_a,
                    out_dir=alloc_step_dir("E-Stop While Weapon Spinning Test"),
                )
            )
        elif args.suite == "drive_e2e":
            results.append(
                do_drive_e2e(
                    repo_root,
                    args.psu_channel,
                    psu_off_first=not args.no_psu_off,
                    drive_forward_axis=args.drive_forward_axis,
                    drive_turn_axis=args.drive_turn_axis,
                    drive_hold_s=args.drive_hold_s,
                    drive_min_delta_us=args.drive_min_delta_us,
                    out_dir=alloc_step_dir("Drive E2E Test"),
                )
            )
        elif args.suite == "disconnect_failsafe":
            results.append(
                do_disconnect_failsafe(
                    repo_root,
                    args.psu_channel,
                    psu_off_first=not args.no_psu_off,
                    drive_forward_axis=args.drive_forward_axis,
                    drive_min_delta_us=args.drive_min_delta_us,
                    out_dir=alloc_step_dir("Disconnect Failsafe Test"),
                )
            )
        elif args.suite == "drive_spin":
            results.append(
                do_drive_spin(
                    repo_root,
                    args.psu_drive_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    drive_forward_axis=args.drive_forward_axis,
                    drive_turn_axis=args.drive_turn_axis,
                    drive_hold_s=args.drive_spin_hold_s,
                    drive_sample_interval_s=args.drive_spin_sample_interval_s,
                    drive_settle_s=args.drive_spin_settle_s,
                    drive_current_delta_a=args.drive_spin_current_delta_a,
                    drive_min_current_a=args.drive_spin_min_current_a,
                    drive_return_tol_a=args.drive_spin_return_tol_a,
                    out_dir=alloc_step_dir("Drive Spin Test"),
                )
            )
        elif args.suite == "estop_drive":
            results.append(
                do_estop_drive(
                    repo_root,
                    args.psu_drive_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    drive_forward_axis=args.drive_forward_axis,
                    drive_hold_s=args.drive_spin_hold_s,
                    drive_sample_interval_s=args.drive_spin_sample_interval_s,
                    drive_settle_s=args.drive_spin_settle_s,
                    drive_current_delta_a=args.drive_spin_current_delta_a,
                    drive_min_current_a=args.drive_spin_min_current_a,
                    drive_return_tol_a=args.drive_spin_return_tol_a,
                    out_dir=alloc_step_dir("E-Stop While Driving Test"),
                )
            )
        elif args.suite == "weapon_spin":
            results.append(
                do_weapon_spin(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    spin_axis=args.spin_axis,
                    spin_hold_s=args.spin_hold_s,
                    spin_baseline_s=args.spin_baseline_s,
                    spin_sample_interval_s=args.spin_sample_interval_s,
                    spin_settle_s=args.spin_settle_s,
                    spin_current_delta_a=args.spin_current_delta_a,
                    spin_min_current_a=args.spin_min_current_a,
                    require_telemetry=args.require_telemetry,
                    telem_min_rpm=args.telem_min_rpm,
                    out_dir=alloc_step_dir("Weapon Spin Test"),
                )
            )
        elif args.suite == "weapon_zero_cross":
            results.append(
                do_weapon_zero_cross(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    zero_cross_axis=args.zero_cross_axis,
                    zero_cross_hold_s=args.zero_cross_hold_s,
                    zero_cross_max_ms=args.zero_cross_max_ms,
                    zero_cross_cycles=args.zero_cross_cycles,
                    out_dir=alloc_step_dir("Weapon Zero Cross Test"),
                )
            )
        elif args.suite == "weapon_latency":
            results.append(
                do_weapon_latency(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    spin_axis=args.spin_axis,
                    spin_axis_seq=spin_axis_seq,
                    latency_baseline_s=args.latency_baseline_s,
                    latency_hold_s=args.latency_hold_s,
                    latency_cycles=args.latency_cycles,
                    latency_rpm_threshold=args.latency_rpm_threshold,
                    latency_telem_rate_ms=args.latency_telem_rate_ms,
                    latency_status_rate_ms=args.latency_status_rate_ms,
                    out_dir=alloc_step_dir("Weapon Latency Test"),
                )
            )
        elif args.suite == "latency_soak":
            results.append(
                do_weapon_latency(
                    repo_root,
                    args.psu_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    spin_axis=args.soak_axis,
                    spin_axis_seq=[args.soak_axis],
                    latency_baseline_s=args.soak_baseline_s,
                    latency_hold_s=args.soak_hold_s,
                    latency_cycles=args.soak_cycles,
                    latency_rpm_threshold=args.latency_rpm_threshold,
                    latency_telem_rate_ms=args.latency_telem_rate_ms,
                    latency_status_rate_ms=args.latency_status_rate_ms,
                    check_drift=True,
                    max_drift_ms_per_cycle=args.soak_max_drift_ms,
                    max_latency_ms=args.soak_max_latency_ms,
                    out_dir=alloc_step_dir("Latency Soak Test"),
                )
            )
        elif args.suite == "safety_active":
            results.append(
                do_estop_drive(
                    repo_root,
                    args.psu_drive_channel,
                    args.psu_voltage,
                    args.psu_current,
                    psu_off_first=not args.no_psu_off,
                    leave_psu_on=args.leave_psu_on,
                    drive_forward_axis=args.drive_forward_axis,
                    drive_hold_s=args.drive_spin_hold_s,
                    drive_sample_interval_s=args.drive_spin_sample_interval_s,
                    drive_settle_s=args.drive_spin_settle_s,
                    drive_current_delta_a=args.drive_spin_current_delta_a,
                    drive_min_current_a=args.drive_spin_min_current_a,
                    drive_return_tol_a=args.drive_spin_return_tol_a,
                    out_dir=alloc_step_dir("E-Stop While Driving Test"),
                )
            )
            if results[-1].ok:
                results.append(
                    do_disconnect_failsafe(
                        repo_root,
                        args.psu_channel,
                        psu_off_first=not args.no_psu_off,
                        drive_forward_axis=args.drive_forward_axis,
                        drive_min_delta_us=args.drive_min_delta_us,
                        out_dir=alloc_step_dir("Disconnect Failsafe Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_weapon_disarmed_guard(
                        repo_root,
                        args.psu_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        guard_axis=args.guard_axis,
                        guard_hold_s=args.guard_hold_s,
                        guard_baseline_s=args.guard_baseline_s,
                        guard_sample_interval_s=args.guard_sample_interval_s,
                        guard_max_delta_a=args.guard_max_delta_a,
                        out_dir=alloc_step_dir("Weapon Disarmed Guard Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_estop_weapon(
                        repo_root,
                        args.psu_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        spin_axis=args.spin_axis,
                        spin_hold_s=args.spin_hold_s,
                        spin_baseline_s=args.spin_baseline_s,
                        spin_sample_interval_s=args.spin_sample_interval_s,
                        spin_settle_s=args.spin_settle_s,
                        spin_current_delta_a=args.spin_current_delta_a,
                        spin_min_current_a=args.spin_min_current_a,
                        spin_return_tol_a=args.spin_return_tol_a,
                        out_dir=alloc_step_dir("E-Stop While Weapon Spinning Test"),
                    )
                )
        elif args.suite == "full_e2e":
            results.append(
                do_smoke(
                    repo_root,
                    args.psu_channel,
                    psu_off_first=not args.no_psu_off,
                    out_dir=alloc_step_dir("Smoke Test"),
                )
            )
            if results[-1].ok:
                results.append(
                    do_drive_e2e(
                        repo_root,
                        args.psu_channel,
                        psu_off_first=not args.no_psu_off,
                        drive_forward_axis=args.drive_forward_axis,
                        drive_turn_axis=args.drive_turn_axis,
                        drive_hold_s=args.drive_hold_s,
                        drive_min_delta_us=args.drive_min_delta_us,
                        out_dir=alloc_step_dir("Drive E2E Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_drive_spin(
                        repo_root,
                        args.psu_drive_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        drive_forward_axis=args.drive_forward_axis,
                        drive_turn_axis=args.drive_turn_axis,
                        drive_hold_s=args.drive_spin_hold_s,
                        drive_sample_interval_s=args.drive_spin_sample_interval_s,
                        drive_settle_s=args.drive_spin_settle_s,
                        drive_current_delta_a=args.drive_spin_current_delta_a,
                        drive_min_current_a=args.drive_spin_min_current_a,
                        drive_return_tol_a=args.drive_spin_return_tol_a,
                        out_dir=alloc_step_dir("Drive Spin Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_estop_drive(
                        repo_root,
                        args.psu_drive_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        drive_forward_axis=args.drive_forward_axis,
                        drive_hold_s=args.drive_spin_hold_s,
                        drive_sample_interval_s=args.drive_spin_sample_interval_s,
                        drive_settle_s=args.drive_spin_settle_s,
                        drive_current_delta_a=args.drive_spin_current_delta_a,
                        drive_min_current_a=args.drive_spin_min_current_a,
                        drive_return_tol_a=args.drive_spin_return_tol_a,
                        out_dir=alloc_step_dir("E-Stop While Driving Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_disconnect_failsafe(
                        repo_root,
                        args.psu_channel,
                        psu_off_first=not args.no_psu_off,
                        drive_forward_axis=args.drive_forward_axis,
                        drive_min_delta_us=args.drive_min_delta_us,
                        out_dir=alloc_step_dir("Disconnect Failsafe Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_weapon_disarmed_guard(
                        repo_root,
                        args.psu_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        guard_axis=args.guard_axis,
                        guard_hold_s=args.guard_hold_s,
                        guard_baseline_s=args.guard_baseline_s,
                        guard_sample_interval_s=args.guard_sample_interval_s,
                        guard_max_delta_a=args.guard_max_delta_a,
                        out_dir=alloc_step_dir("Weapon Disarmed Guard Test"),
                    )
                )
            if results[-1].ok:
                results.append(
                    do_weapon_spin(
                        repo_root,
                        args.psu_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        spin_axis=args.spin_axis,
                        spin_hold_s=args.spin_hold_s,
                        spin_baseline_s=args.spin_baseline_s,
                    spin_sample_interval_s=args.spin_sample_interval_s,
                    spin_settle_s=args.spin_settle_s,
                    spin_current_delta_a=args.spin_current_delta_a,
                    spin_min_current_a=args.spin_min_current_a,
                    require_telemetry=args.require_telemetry,
                    telem_min_rpm=args.telem_min_rpm,
                    out_dir=alloc_step_dir("Weapon Spin Test"),
                )
            )
            if results[-1].ok:
                results.append(
                    do_estop_weapon(
                        repo_root,
                        args.psu_channel,
                        args.psu_voltage,
                        args.psu_current,
                        psu_off_first=not args.no_psu_off,
                        leave_psu_on=args.leave_psu_on,
                        spin_axis=args.spin_axis,
                        spin_hold_s=args.spin_hold_s,
                        spin_baseline_s=args.spin_baseline_s,
                        spin_sample_interval_s=args.spin_sample_interval_s,
                        spin_settle_s=args.spin_settle_s,
                        spin_current_delta_a=args.spin_current_delta_a,
                        spin_min_current_a=args.spin_min_current_a,
                        spin_return_tol_a=args.spin_return_tol_a,
                        out_dir=alloc_step_dir("E-Stop While Weapon Spinning Test"),
                    )
                )

        if results and not results[-1].ok:
            exit_code = 1

    report = {
        "started_at": run_started_at,
        "finished_at": now_iso(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "suite": args.suite,
        "argv": sys.argv,
        "args": vars(args),
        "git": git_meta,
        "devices": device_meta,
        "psu": psu_meta,
        "results": [r.__dict__ for r in results],
        "ok": all(r.ok for r in results),
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "orchestrator_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    latest_path = repo_root / "hitl_logs" / "latest_orchestrator_report.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (repo_root / "hitl_logs" / "latest_run_dir.txt").write_text(str(run_dir) + "\n", encoding="utf-8")

    if not args.no_report:
        venv_py = repo_root / ".venv" / "bin" / "python3"
        report_py = repo_root / "tools" / "hitl_report.py"
        if venv_py.exists() and report_py.exists():
            gen = run_cmd([str(venv_py), str(report_py), "--run-dir", str(run_dir)], check=False, capture_output=True)
            (run_dir / "report_gen.log").write_text(
                (gen.stdout or "") + ("\n" + gen.stderr if gen.stderr else ""),
                encoding="utf-8",
            )
        else:
            (run_dir / "report_gen.log").write_text(
                f"report generation skipped (venv_py_exists={venv_py.exists()} report_py_exists={report_py.exists()})\n",
                encoding="utf-8",
            )

    if report["ok"]:
        print("HITL: PASS")
        print(f"HITL artifacts: {run_dir}")
        sys.exit(0)
    print("HITL: FAIL")
    print(f"HITL artifacts: {run_dir}")
    for r in results:
        if not r.ok:
            print(f"- {r.name}: {r.detail}")
    sys.exit(1)


if __name__ == "__main__":
    main()
