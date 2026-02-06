#!/usr/bin/env python3
"""
Run a serial HITL sequence against thumbsup_serial and log telemetry.
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    print(f"Missing pyserial: {exc}")
    sys.exit(1)


TELEM_RE = re.compile(
    r"^TELEM valid=(\d+) age=(--|\d+)"
    r"(?: erpm=(\d+) rpm=(\d+) V=([0-9.]+) I=([0-9.]+) T=(\d+))?"
)


def find_pico_port(product_hint=None):
    if product_hint is None:
        hitl = Path("/dev/ttyHITL_ROBOT")
        if hitl.exists():
            return str(hitl)
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if product_hint:
            product = (port.product or "").lower()
            description = (port.description or "").lower()
            if product_hint.lower() not in product and product_hint.lower() not in description:
                continue
        if "2E8A" in port.hwid or "Pico" in port.description or "RP2040" in port.description:
            return port.device
    return None


def format_wall(start_wall, t_s):
    return (start_wall + timedelta(seconds=t_s)).isoformat(timespec="milliseconds")


def parse_steps(value):
    if not value:
        return []
    return [int(chunk.strip()) for chunk in value.split(",") if chunk.strip()]


def write_tx(log_handle, t_s, line):
    wall = format_wall(START_WALL, t_s)
    log_handle.write(f"{t_s:.3f}\t{wall}\tTX\t{line}\n")


def handle_rx(line, t_s, log_handle, telem_writer, throttle):
    wall = format_wall(START_WALL, t_s)
    log_handle.write(f"{t_s:.3f}\t{wall}\tRX\t{line}\n")

    match = TELEM_RE.match(line)
    if not match:
        return

    valid = int(match.group(1))
    age = match.group(2)
    erpm = match.group(3)
    rpm = match.group(4)
    volt = match.group(5)
    curr = match.group(6)
    temp = match.group(7)

    telem_writer.writerow([
        f"{t_s:.3f}",
        wall,
        throttle,
        valid,
        "" if age == "--" else age,
        "" if erpm is None else erpm,
        "" if rpm is None else rpm,
        "" if volt is None else volt,
        "" if curr is None else curr,
        "" if temp is None else temp,
        line,
    ])


def pump_serial(ser, log_handle, telem_writer, throttle, max_time_s=0.05, max_lines=50):
    start = time.monotonic()
    lines = 0
    while (time.monotonic() - start) < max_time_s and lines < max_lines:
        raw = ser.readline()
        if not raw:
            return
        text = raw.decode("utf-8", errors="replace").rstrip()
        now = time.monotonic() - START_MONO
        handle_rx(text, now, log_handle, telem_writer, throttle)
        lines += 1


def send_line(ser, log_handle, line):
    now = time.monotonic() - START_MONO
    try:
        ser.write((line + "\n").encode("utf-8"))
    except serial.SerialTimeoutException:
        time.sleep(0.2)
        ser.write((line + "\n").encode("utf-8"))
    write_tx(log_handle, now, line)


def hold_command(ser, log_handle, telem_writer, line, duration_s,
                 keepalive_s, telemetry_s, throttle):
    start = time.monotonic()
    next_send = start
    next_telem = start

    while time.monotonic() - start < duration_s:
        now = time.monotonic()
        if now >= next_send:
            send_line(ser, log_handle, line)
            next_send += keepalive_s

        if telemetry_s > 0 and now >= next_telem:
            send_line(ser, log_handle, "TELEM")
            next_telem += telemetry_s

        pump_serial(ser, log_handle, telem_writer, throttle)
        time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description="Run a serial HITL throttle ramp.")
    parser.add_argument("--port", help="serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--auto", action="store_true", help="auto-detect Pico serial port")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud rate")
    parser.add_argument("--product", help="substring to match USB product string")
    parser.add_argument("--steps", default="20,40,60,80",
                        help="comma-separated throttle steps (percent)")
    parser.add_argument("--hold", type=float, default=3.0, help="seconds per step")
    parser.add_argument("--cooldown", type=float, default=2.0, help="seconds at zero before estop")
    parser.add_argument("--telemetry-interval", type=float, default=0.5,
                        help="seconds between TELEM polls (0 to disable)")
    parser.add_argument("--keepalive-interval", type=float, default=0.1,
                        help="seconds between command re-sends")
    parser.add_argument("--arm-direct", action="store_true",
                        help="use ARM_ON/ARM_OFF instead of ARM")
    parser.add_argument("--weapon-direct", action="store_true",
                        help="use WEAPON_SPEED instead of THROTTLE")
    parser.add_argument("--arm-delay", type=float, default=9.0,
                        help="seconds to hold throttle 0 after arming")
    parser.add_argument("--out-dir", default="hitl_logs", help="output directory root")
    parser.add_argument("--label", default="serial_hitl", help="output label prefix")
    parser.add_argument("--warmup", type=float, default=2.0,
                        help="seconds to drain startup output before sending commands")
    args = parser.parse_args()

    port = args.port
    if not port and args.auto:
        port = find_pico_port(args.product)
    if not port:
        print("No serial port specified. Use --port or --auto.")
        sys.exit(1)

    out_dir = Path(args.out_dir) / f"{args.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    serial_log_path = out_dir / "serial.log"
    telemetry_path = out_dir / "telemetry.csv"

    steps = parse_steps(args.steps)
    if not steps:
        print("No throttle steps provided.")
        sys.exit(1)

    print(f"Opening serial {port} @ {args.baud}...")

    global START_MONO, START_WALL
    START_MONO = time.monotonic()
    START_WALL = datetime.now()

    with serial.Serial(port, args.baud, timeout=0.05, write_timeout=1.0) as ser, \
            open(serial_log_path, "w", encoding="utf-8") as log_handle, \
            open(telemetry_path, "w", newline="") as telem_handle:
        telem_writer = csv.writer(telem_handle)
        telem_writer.writerow([
            "t_s",
            "wall_time",
            "throttle_pct",
            "valid",
            "age_ms",
            "erpm",
            "rpm",
            "esc_voltage_v",
            "esc_current_a",
            "esc_temp_c",
            "raw_line",
        ])

        warmup_end = time.monotonic() + args.warmup
        while time.monotonic() < warmup_end:
            pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)
            time.sleep(0.05)

        send_line(ser, log_handle, "RESET")
        send_line(ser, log_handle, "SYS")
        pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)

        if args.arm_direct:
            send_line(ser, log_handle, "ARM_OFF")
            pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)

        arm_cmd = "ARM_ON" if args.arm_direct else "ARM"
        send_line(ser, log_handle, arm_cmd)
        pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)
        throttle_cmd = "WEAPON_SPEED" if args.weapon_direct else "THROTTLE"

        if args.arm_delay > 0:
            print(f"Holding throttle 0% for {args.arm_delay:.1f}s after arming")
            hold_command(
                ser,
                log_handle,
                telem_writer,
                f"{throttle_cmd} 0",
                args.arm_delay,
                args.keepalive_interval,
                0,
                0,
            )

        for step in steps:
            print(f"Holding throttle {step}% for {args.hold:.1f}s")
            hold_command(
                ser,
                log_handle,
                telem_writer,
                f"{throttle_cmd} {step}",
                args.hold,
                args.keepalive_interval,
                args.telemetry_interval,
                step,
            )

        if args.cooldown > 0:
            print(f"Cooldown throttle 0% for {args.cooldown:.1f}s")
            hold_command(
                ser,
                log_handle,
                telem_writer,
                f"{throttle_cmd} 0",
                args.cooldown,
                args.keepalive_interval,
                args.telemetry_interval,
                0,
            )

        print("Triggering ESTOP")
        send_line(ser, log_handle, "ESTOP")
        time.sleep(0.2)
        pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)

        print("Clearing ESTOP")
        send_line(ser, log_handle, "CLEAR_ESTOP")
        time.sleep(0.2)
        pump_serial(ser, log_handle, telem_writer, 0)
        if args.arm_direct:
            send_line(ser, log_handle, "ARM_OFF")
            pump_serial(ser, log_handle, telem_writer, 0, max_time_s=0.2, max_lines=200)

        send_line(ser, log_handle, "SYS")
        pump_serial(ser, log_handle, telem_writer, 0)

    print(f"Saved serial log: {serial_log_path}")
    print(f"Saved telemetry log: {telemetry_path}")


if __name__ == "__main__":
    main()
