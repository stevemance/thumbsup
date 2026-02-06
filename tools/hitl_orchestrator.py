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


HITL_STATUS_RE = re.compile(r"^HITL STATUS (.+)$")
HITL_EVENT_RE = re.compile(r"^HITL EVENT (.+)$")
HITL_BTADDR_RE = re.compile(r"^HITL BTADDR ([0-9A-Fa-f:]{17})$")
LSUSB_RP2_BOOT_RE = re.compile(r"^Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+2e8a:0003\b")


def run_cmd(
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args,
        capture_output=capture_output,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(args)}\n{detail}")
    return result


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


def resolve_robot_port() -> str:
    port = find_port_by_symlink("/dev/ttyHITL_ROBOT")
    if port:
        return port
    port = find_port_by_product("ThumbsUp HITL Robot")
    if port:
        return port
    raise RuntimeError("could not find robot serial port (expected /dev/ttyHITL_ROBOT or USB product match)")


def resolve_gamepad_port() -> str:
    port = find_port_by_symlink("/dev/ttyHITL_GAMEPAD")
    if port:
        return port
    port = find_port_by_product("ThumbsUp HITL Gamepad")
    if port:
        return port
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


def picotool_flash_via_reset(usb_serial: str, uf2_path: str) -> None:
    if not Path(uf2_path).exists():
        raise RuntimeError(f"missing UF2: {uf2_path}")

    before = lsusb_rp2_bootsel_devices()
    run_cmd(["picotool", "reboot", "-u", "-f", "--ser", usb_serial], check=True, capture_output=True)
    bus, addr = wait_for_new_rp2_bootsel_device(before, timeout_s=10.0)
    run_cmd(
        ["picotool", "load", "-x", uf2_path, "--bus", str(bus), "--address", str(addr)],
        check=True,
        capture_output=False,
    )


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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str
    started_at: str
    finished_at: str


def parse_kv_payload(payload: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in payload.strip().split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k] = v
    return out


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
) -> dict[str, str]:
    deadline = time.monotonic() + timeout_s
    last_status: dict[str, str] = {}
    while time.monotonic() < deadline:
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


def step(name: str):
    def deco(fn):
        def wrapped(*args, **kwargs):
            started = now_iso()
            try:
                detail = fn(*args, **kwargs)
                return StepResult(name=name, ok=True, detail=detail or "ok", started_at=started, finished_at=now_iso())
            except Exception as exc:
                return StepResult(name=name, ok=False, detail=str(exc), started_at=started, finished_at=now_iso())
        return wrapped
    return deco


@step("Build Firmware")
def do_build(repo_root: Path, build_robot_fw: bool, build_gamepad_fw: bool) -> str:
    if build_robot_fw:
        build_robot(repo_root)
    if build_gamepad_fw:
        build_gamepad(repo_root)
    return "built"


@step("Flash Firmware")
def do_flash(repo_root: Path, flash_robot: bool, flash_gamepad: bool) -> str:
    # Resolve current tty devices to read their application-mode USB serials.
    if flash_robot:
        robot_tty = resolve_robot_port()
        robot_usb_ser = get_usb_serial_for_tty(robot_tty)
        picotool_flash_via_reset(robot_usb_ser, str(repo_root / "firmware" / "build" / "thumbsup_hitl.uf2"))
        wait_for_tty_ready("/dev/ttyHITL_ROBOT", 10)

    if flash_gamepad:
        gamepad_tty = resolve_gamepad_port()
        gamepad_usb_ser = get_usb_serial_for_tty(gamepad_tty)
        picotool_flash_via_reset(
            gamepad_usb_ser, str(repo_root / "controller_emulator" / "build" / "thumbsup_controller_emulator.uf2")
        )
        wait_for_tty_ready("/dev/ttyHITL_GAMEPAD", 10)

    return "flashed"


@step("Smoke Test")
def do_smoke(repo_root: Path, psu_channel: int | None, psu_off_first: bool) -> str:
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
        out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")

        # Drain startup noise.
        start = time.monotonic()
        while time.monotonic() - start < 3.0:
            robot_log.read_line()
            gamepad_log.read_line()

        # Put both devices into a deterministic state.
        gamepad_log.send_line("RESET")

        # Wait for at least one status sample so we know the HITL console tick is alive.
        wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s)

        # Force a safe, deterministic battery voltage for HITL.
        robot_log.send_line("HITL BATTERY 12500")
        wait_for_robot_condition(
            robot_log,
            timeout_s=3.0,
            predicate=lambda s: s.get("batt_mv") == "12500",
        )

        # Ensure controller connects (gamepad initiates).
        robot_log.send_line("HITL BTADDR")
        btaddr = wait_for_robot_btaddr(robot_log, timeout_s=5.0)
        gamepad_log.send_line(f"CONNECT {btaddr}")
        # Prefer status field "ready=1" since printf output can interleave and corrupt event lines.
        # Try once without clearing keys (stable pairing is more reliable). If it doesn't connect,
        # fall back to wiping keys and retrying to force a fresh pair.
        try:
            wait_for_robot_condition(
                robot_log,
                timeout_s=20.0,
                predicate=lambda s: s.get("ready") == "1" or s.get("controller_ready") == "1",
            )
        except RuntimeError:
            robot_log.send_line("HITL BTKEYS CLEAR")
            gamepad_log.send_line("KEYS CLEAR")
            time.sleep(0.5)
            gamepad_log.send_line(f"CONNECT {btaddr}")
            wait_for_robot_condition(
                robot_log,
                timeout_s=40.0,
                predicate=lambda s: s.get("ready") == "1" or s.get("controller_ready") == "1",
            )

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
        out_dir = repo_root / "hitl_logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)

        robot_log = SerialLogger(robot_ser, out_dir / "robot_serial.log", "ROBOT")
        gamepad_log = SerialLogger(gamepad_ser, out_dir / "gamepad_serial.log", "GAMEPAD")

        def cleanup_best_effort() -> None:
            try:
                gamepad_log.send_line("AXIS RY 0")
                gamepad_log.send_line("BTN A 0")
                gamepad_log.send_line("BTN B 0")
                gamepad_log.send_line("BTN L1 0")
                gamepad_log.send_line("BTN R1 0")
                # Toggle B to try to disarm if we're armed.
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
            wait_for_robot_condition(robot_log, timeout_s=12.0, predicate=lambda s: "t_ms" in s)

            # Force a safe, deterministic battery voltage for HITL.
            robot_log.send_line("HITL BATTERY 12500")
            wait_for_robot_condition(
                robot_log,
                timeout_s=3.0,
                predicate=lambda s: s.get("batt_mv") == "12500",
            )

            # Ensure controller connects (gamepad initiates).
            robot_log.send_line("HITL BTADDR")
            btaddr = wait_for_robot_btaddr(robot_log, timeout_s=5.0)
            gamepad_log.send_line(f"CONNECT {btaddr}")
            try:
                wait_for_robot_condition(
                    robot_log,
                    timeout_s=20.0,
                    predicate=lambda s: s.get("ready") == "1" or s.get("controller_ready") == "1",
                )
            except RuntimeError:
                robot_log.send_line("HITL BTKEYS CLEAR")
                gamepad_log.send_line("KEYS CLEAR")
                time.sleep(0.5)
                gamepad_log.send_line(f"CONNECT {btaddr}")
                wait_for_robot_condition(
                    robot_log,
                    timeout_s=40.0,
                    predicate=lambda s: s.get("ready") == "1" or s.get("controller_ready") == "1",
                )

            # Arm toggle with B.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=3.0, predicate=lambda s: s.get("armed") == "1")

            # Wait for weapon state machine to finish arming (DShot setup can take a few seconds).
            wait_for_robot_condition(
                robot_log,
                timeout_s=20.0,
                predicate=lambda s: s.get("weapon") in ("ARMED", "SPINNING"),
            )

            # Spin at a safe low command for a short hold.
            spin_axis = max(-127, min(127, int(spin_axis)))
            if spin_axis < 0:
                spin_axis = 0
            gamepad_log.send_line(f"AXIS RY {spin_axis}")

            def telemetry_rpm_ok(s: dict[str, str]) -> bool:
                if s.get("telem") != "1":
                    return False
                rpm_s = s.get("rpm")
                if not rpm_s:
                    return False
                try:
                    rpm = int(rpm_s)
                except ValueError:
                    return False
                return rpm > 0

            wait_for_robot_condition(robot_log, timeout_s=10.0, predicate=telemetry_rpm_ok)

            # Hold spin.
            time.sleep(max(0.0, float(spin_hold_s)))

            # Stop.
            gamepad_log.send_line("AXIS RY 0")
            wait_for_robot_condition(robot_log, timeout_s=10.0, predicate=lambda s: s.get("speed") == "0")

            # Disarm.
            time.sleep(0.2)  # Respect debounce timing in firmware.
            gamepad_log.send_line("BTN B 1")
            time.sleep(0.12)
            gamepad_log.send_line("BTN B 0")
            wait_for_robot_condition(robot_log, timeout_s=5.0, predicate=lambda s: s.get("armed") == "0")

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

        finally:
            cleanup_best_effort()
            robot_log.close()
            gamepad_log.close()

    return "weapon spin passed"


def main() -> None:
    parser = argparse.ArgumentParser(description="ThumbsUp HITL orchestrator")
    parser.add_argument("--no-build", action="store_true", help="skip firmware builds")
    parser.add_argument("--no-flash", action="store_true", help="skip flashing")
    parser.add_argument("--no-psu-off", action="store_true", help="do not force PSU off at start")
    parser.add_argument("--psu-channel", type=int, default=1, help="PSU channel (Rigol DP832)")
    parser.add_argument("--psu-voltage", type=float, default=12.6, help="PSU voltage for active motor tests")
    parser.add_argument("--psu-current", type=float, default=5.0, help="PSU current limit for active motor tests")
    parser.add_argument("--leave-psu-on", action="store_true", help="leave PSU output enabled after suite")
    parser.add_argument("--spin-axis", type=int, default=20, help="Weapon spin command (RY axis -127..127)")
    parser.add_argument("--spin-hold-s", type=float, default=5.0, help="Seconds to hold weapon command")
    parser.add_argument("--suite", choices=["smoke", "weapon_spin"], default="smoke")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]

    results: list[StepResult] = []

    if not args.no_build:
        results.append(do_build(repo_root, build_robot_fw=True, build_gamepad_fw=True))

    if not args.no_flash:
        results.append(do_flash(repo_root, flash_robot=True, flash_gamepad=True))
        if not results[-1].ok:
            # Don't attempt to run tests if the devices might be in BOOTSEL.
            report = {
                "started_at": now_iso(),
                "suite": args.suite,
                "results": [r.__dict__ for r in results],
                "ok": False,
            }
            report_path = repo_root / "hitl_logs" / "latest_orchestrator_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("HITL: FAIL")
            print(f"- Flash Firmware: {results[-1].detail}")
            sys.exit(1)

    if args.suite == "smoke":
        results.append(do_smoke(repo_root, args.psu_channel, psu_off_first=not args.no_psu_off))
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
            )
        )

    report = {
        "started_at": now_iso(),
        "suite": args.suite,
        "results": [r.__dict__ for r in results],
        "ok": all(r.ok for r in results),
    }

    report_path = repo_root / "hitl_logs" / "latest_orchestrator_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if report["ok"]:
        print("HITL: PASS")
        sys.exit(0)
    print("HITL: FAIL")
    for r in results:
        if not r.ok:
            print(f"- {r.name}: {r.detail}")
    sys.exit(1)


if __name__ == "__main__":
    main()
