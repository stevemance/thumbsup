#!/usr/bin/env python3
"""
Capture DShot telemetry with timestamps, log PSU samples, and summarize
trimmed medians per step.
"""

import argparse
import csv
import json
import re
import statistics
import subprocess
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


CYCLE_RE = re.compile(r"^=== Cycle\s+(\d+)")
STEP_START_RE = re.compile(r"STEP_START index=(\d+) throttle=(\d+) hold=(\d+)ms")
STEP_END_RE = re.compile(r"STEP_END index=(\d+) throttle=(\d+)")
RPM_SAMPLE_RE = re.compile(
    r"RPM_SAMPLE throttle=(\d+) "
    r"(?:(?:erpm=(\d+) rpm=(\d+)"
    r"(?: path=([a-z]+) inv=(\d+) pick=([a-z]+)(?: off=(\d+))?)?)|erpm=-- rpm=--) "
    r"V=([0-9.\-]+|--) I=([0-9.\-]+|--) T=([0-9\-]+|--)"
)


def find_pico_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "2E8A" in port.hwid or "Pico" in port.description or "RP2040" in port.description:
            return port.device
    return None


def read_psu_snapshot(channel):
    result = subprocess.run(
        ["labctl", "--json", "psu", "snapshot", "--channel", str(channel)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, (result.stderr.strip() or result.stdout.strip())

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"json error: {exc} ({result.stdout.strip()})"

    if not payload.get("ok"):
        return None, "snapshot failed"

    values = payload.get("values", {}).get(str(channel), {})
    if not values:
        return None, "no channel data"

    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    voltage = to_float(values.get("voltage"))
    current = to_float(values.get("current"))
    power = to_float(values.get("power"))
    status = values.get("status", "")
    return (voltage, current, power, status), None


def decode_line(raw):
    try:
        return raw.decode("utf-8").rstrip()
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace").rstrip()


def median_or_none(values):
    if not values:
        return None
    return statistics.median(values)


def parse_rpm_sample(line):
    match = RPM_SAMPLE_RE.search(line)
    if not match:
        return None

    throttle = int(match.group(1))
    erpm = match.group(2)
    rpm = match.group(3)
    path = match.group(4)
    inv = match.group(5)
    pick = match.group(6)
    offset = match.group(7)
    voltage = match.group(8)
    current = match.group(9)
    temp = match.group(10)

    def to_int(value):
        return int(value) if value is not None else None

    def to_float(value):
        if value is None or value == "--":
            return None
        return float(value)

    def to_temp(value):
        if value is None or value == "--":
            return None
        return int(value)

    return {
        "throttle": throttle,
        "erpm": to_int(erpm),
        "rpm": to_int(rpm),
        "path": path,
        "invert": None if inv is None else int(inv),
        "pick": pick,
        "sample_offset": None if offset is None else int(offset),
        "esc_voltage": to_float(voltage),
        "esc_current": to_float(current),
        "esc_temp": to_temp(temp),
    }


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)


def format_wall(start_wall, t_s):
    return (start_wall + timedelta(seconds=t_s)).isoformat(timespec="milliseconds")


def summarize_steps(steps, psu_samples, trim_s, summary_path):
    with open(summary_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "cycle",
            "step_index",
            "throttle",
            "start_s",
            "end_s",
            "duration_s",
            "trim_s",
            "rpm_median",
            "erpm_median",
            "esc_voltage_median",
            "esc_current_median",
            "esc_temp_median",
            "telemetry_samples_total",
            "telemetry_samples_used",
            "psu_voltage_median",
            "psu_current_median",
            "psu_samples_total",
            "psu_samples_used",
        ])

        for step in steps:
            if step.get("end_s") is None:
                continue

            start_s = step["start_s"]
            end_s = step["end_s"]
            duration = max(0.0, end_s - start_s)
            window_start = start_s + trim_s
            window_end = end_s - trim_s
            if window_end <= window_start:
                window_start = start_s
                window_end = end_s

            samples = step.get("samples", [])
            telemetry_window = [s for s in samples if window_start <= s["t_s"] <= window_end]
            if not telemetry_window:
                telemetry_window = samples

            rpm_vals = [s["rpm"] for s in telemetry_window if s["rpm"] is not None]
            erpm_vals = [s["erpm"] for s in telemetry_window if s["erpm"] is not None]
            esc_v = [s["esc_voltage"] for s in telemetry_window if s["esc_voltage"] is not None]
            esc_i = [s["esc_current"] for s in telemetry_window if s["esc_current"] is not None]
            esc_t = [s["esc_temp"] for s in telemetry_window if s["esc_temp"] is not None]

            psu_window = [s for s in psu_samples if window_start <= s["t_s"] <= window_end]
            if not psu_window:
                psu_window = [s for s in psu_samples if start_s <= s["t_s"] <= end_s]
            psu_v = [s["voltage"] for s in psu_window if s["voltage"] is not None]
            psu_i = [s["current"] for s in psu_window if s["current"] is not None]

            writer.writerow([
                step.get("cycle"),
                step.get("index"),
                step.get("throttle"),
                f"{start_s:.3f}",
                f"{end_s:.3f}",
                f"{duration:.3f}",
                f"{trim_s:.2f}",
                median_or_none(rpm_vals),
                median_or_none(erpm_vals),
                median_or_none(esc_v),
                median_or_none(esc_i),
                median_or_none(esc_t),
                len(samples),
                len(telemetry_window),
                median_or_none(psu_v),
                median_or_none(psu_i),
                len(psu_samples),
                len(psu_window),
            ])


def main():
    parser = argparse.ArgumentParser(
        description="Capture DShot telemetry and PSU logs with trimmed median summary."
    )
    parser.add_argument("--port", help="serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud rate")
    parser.add_argument("--auto", action="store_true", help="auto-detect Pico serial port")
    parser.add_argument("--cycles", type=int, default=1,
                        help="number of telemetry cycles to capture (0 = unlimited)")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="stop after duration seconds (0 = ignore)")
    parser.add_argument("--trim", type=float, default=5.0,
                        help="seconds to trim from step start/end")
    parser.add_argument("--psu-channel", type=int, default=1, help="PSU channel")
    parser.add_argument("--psu-interval", type=float, default=0.5, help="PSU sample interval (s)")
    parser.add_argument("--no-psu", action="store_true", help="skip PSU logging")
    parser.add_argument("--out-dir", default="./calibration_logs",
                        help="output directory root")
    parser.add_argument("--label", default="telemetry_cal",
                        help="label prefix for output files")
    args = parser.parse_args()

    port = args.port
    if not port and args.auto:
        port = find_pico_port()
    if not port:
        print("No serial port specified. Use --port or --auto.")
        sys.exit(1)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / f"{args.label}_{run_id}"
    ensure_dir(out_dir)

    telemetry_raw_path = out_dir / "telemetry_raw.log"
    telemetry_samples_path = out_dir / "telemetry_samples.csv"
    psu_log_path = out_dir / "psu_log.csv"
    summary_path = out_dir / "summary.csv"

    print(f"Opening serial {port} @ {args.baud}...")

    ser = serial.Serial(port, args.baud, timeout=0.05)
    ser.reset_input_buffer()

    start_wall = datetime.now()
    start_monotonic = time.monotonic()
    next_psu = start_monotonic

    cycle_seen = 0
    steps = []
    current_step = None
    psu_samples = []

    with open(telemetry_raw_path, "w", encoding="utf-8") as raw_handle, \
            open(telemetry_samples_path, "w", newline="") as sample_handle, \
            open(psu_log_path, "w", newline="") as psu_handle:
        sample_writer = csv.writer(sample_handle)
        sample_writer.writerow([
            "t_s",
            "wall_time",
            "cycle",
            "step_index",
            "throttle",
            "erpm",
            "rpm",
            "path",
            "invert",
            "pick",
            "sample_offset",
            "esc_voltage_v",
            "esc_current_a",
            "esc_temp_c",
            "raw_line",
        ])
        psu_writer = csv.writer(psu_handle)
        psu_writer.writerow(["t_s", "wall_time", "voltage_v", "current_a", "power_w", "status", "error"])

        stop_after_cycle = None

        try:
            while True:
                now = time.monotonic()
                elapsed = now - start_monotonic

                if args.duration > 0.0 and elapsed >= args.duration:
                    break

                if not args.no_psu and now >= next_psu:
                    snapshot, err = read_psu_snapshot(args.psu_channel)
                    wall = format_wall(start_wall, elapsed)
                    if snapshot is None:
                        psu_writer.writerow([f"{elapsed:.3f}", wall, "", "", "", "", err])
                    else:
                        voltage, current, power, status = snapshot
                        psu_writer.writerow([
                            f"{elapsed:.3f}",
                            wall,
                            "" if voltage is None else f"{voltage:.3f}",
                            "" if current is None else f"{current:.3f}",
                            "" if power is None else f"{power:.3f}",
                            status,
                            "",
                        ])
                        psu_samples.append({
                            "t_s": elapsed,
                            "voltage": voltage,
                            "current": current,
                        })
                    next_psu += args.psu_interval

                line = ser.readline()
                if line:
                    line_elapsed = time.monotonic() - start_monotonic
                    text = decode_line(line)
                    wall = format_wall(start_wall, line_elapsed)
                    raw_handle.write(f"{line_elapsed:.3f}\t{wall}\t{text}\n")

                    cycle_match = CYCLE_RE.search(text)
                    if cycle_match:
                        cycle_seen = int(cycle_match.group(1))
                        if args.cycles > 0 and cycle_seen > args.cycles:
                            stop_after_cycle = cycle_seen

                    step_match = STEP_START_RE.search(text)
                    if step_match:
                        idx, throttle, hold_ms = map(int, step_match.groups())
                        if cycle_seen == 0:
                            cycle_seen = 1
                        current_step = {
                            "cycle": cycle_seen,
                            "index": idx,
                            "throttle": throttle,
                            "hold_ms": hold_ms,
                            "start_s": line_elapsed,
                            "end_s": None,
                            "samples": [],
                        }
                        steps.append(current_step)

                    end_match = STEP_END_RE.search(text)
                    if end_match:
                        idx = int(end_match.group(1))
                        for step in reversed(steps):
                            if step["end_s"] is None and step["index"] == idx:
                                step["end_s"] = line_elapsed
                                if current_step is step:
                                    current_step = None
                                break

                    sample = parse_rpm_sample(text)
                    if sample:
                        sample.update({
                            "t_s": line_elapsed,
                            "cycle": cycle_seen,
                            "step_index": current_step["index"] if current_step else None,
                        })
                        if current_step:
                            current_step["samples"].append(sample)
                        sample_writer.writerow([
                            f"{line_elapsed:.3f}",
                            wall,
                            cycle_seen,
                            current_step["index"] if current_step else "",
                            sample.get("throttle", ""),
                            sample.get("erpm", ""),
                            sample.get("rpm", ""),
                            sample.get("path", ""),
                            "" if sample.get("invert") is None else sample["invert"],
                            sample.get("pick", ""),
                            "" if sample.get("sample_offset") is None else sample["sample_offset"],
                            "" if sample.get("esc_voltage") is None else f"{sample['esc_voltage']:.2f}",
                            "" if sample.get("esc_current") is None else f"{sample['esc_current']:.2f}",
                            "" if sample.get("esc_temp") is None else sample["esc_temp"],
                            text,
                        ])

                    if stop_after_cycle and (cycle_seen >= stop_after_cycle):
                        break

                if not line:
                    sleep_for = 0.01
                    if not args.no_psu:
                        sleep_for = min(sleep_for, max(0.0, next_psu - time.monotonic()))
                    time.sleep(sleep_for)
        except KeyboardInterrupt:
            pass
        finally:
            ser.close()

    summarize_steps(steps, psu_samples, args.trim, summary_path)

    print(f"Saved telemetry raw log: {telemetry_raw_path}")
    print(f"Saved telemetry samples: {telemetry_samples_path}")
    print(f"Saved PSU log: {psu_log_path}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
