#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
import time


def read_snapshot(channel):
    result = subprocess.run(
        ["labctl", "--json", "psu", "snapshot", "--channel", str(channel)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, f"labctl error: {result.stderr.strip() or result.stdout.strip()}"

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


def log_samples(channel, duration_s, interval_s, out_path):
    start = time.time()
    next_sample = start

    with open(out_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t_s", "voltage_v", "current_a", "power_w", "status", "error"])

        while True:
            now = time.time()
            elapsed = now - start
            if duration_s is not None and elapsed > duration_s:
                break

            if now < next_sample:
                time.sleep(next_sample - now)
                continue

            snapshot, err = read_snapshot(channel)
            if snapshot is None:
                writer.writerow([f"{elapsed:.3f}", "", "", "", "", err])
            else:
                voltage, current, power, status = snapshot
                writer.writerow([
                    f"{elapsed:.3f}",
                    "" if voltage is None else f"{voltage:.3f}",
                    "" if current is None else f"{current:.3f}",
                    "" if power is None else f"{power:.3f}",
                    status,
                    "",
                ])
            handle.flush()

            next_sample += interval_s


def main():
    parser = argparse.ArgumentParser(description="Log PSU voltage/current/power over time.")
    parser.add_argument("--channel", type=int, default=1, help="PSU channel number")
    parser.add_argument("--duration", type=float, default=180.0,
                        help="log duration in seconds (default: 180)")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="sample interval in seconds (default: 0.5)")
    parser.add_argument("--out", default="/tmp/psu_log.csv", help="output CSV path")
    args = parser.parse_args()

    try:
        log_samples(args.channel, args.duration, args.interval, args.out)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
