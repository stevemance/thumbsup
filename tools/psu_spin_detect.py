#!/usr/bin/env python3
import argparse
import subprocess
import time


def read_current(channel):
    result = subprocess.run(
        ["labctl", "psu", "measure", "--channel", str(channel), "--kind", "current"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, (result.stderr.strip() or result.stdout.strip())
    try:
        return float(result.stdout.strip()), None
    except ValueError as exc:
        return None, f"parse error: {exc} ({result.stdout.strip()})"


def sample_current(channel, samples, delay_s, label):
    values = []
    for _ in range(samples):
        value, err = read_current(channel)
        if err:
            print(f"{label}: read error: {err}")
        else:
            values.append(value)
        time.sleep(delay_s)
    if not values:
        return None, None, None
    return min(values), sum(values) / len(values), max(values)


def run_cycle(args, cycle):
    if cycle is not None:
        print(f"\n=== Cycle {cycle} ===")

    print("Sampling PSU current for spin detection...")
    b_min, b_avg, b_max = sample_current(args.channel, args.baseline, args.delay, "baseline")
    print(f"baseline: min={b_min} avg={b_avg} max={b_max} (A)")

    if args.gap > 0:
        print(f"waiting {args.gap:.1f}s before run sampling...")
        time.sleep(args.gap)

    r_min, r_avg, r_max = sample_current(args.channel, args.run, args.delay, "run")
    print(f"run: min={r_min} avg={r_avg} max={r_max} (A)")

    if b_avg is None or r_avg is None:
        print("insufficient data to compute delta")
        return None

    delta = r_avg - b_avg
    print(f"delta avg current: {delta:.3f} A")
    if delta > args.threshold:
        print("likely spinning (delta > threshold)")
    else:
        print("no clear spin signal (delta <= threshold)")
    return delta


def main():
    parser = argparse.ArgumentParser(description="Detect motor spin via PSU current draw.")
    parser.add_argument("--channel", type=int, default=1, help="PSU channel number")
    parser.add_argument("--baseline", type=int, default=20, help="baseline sample count")
    parser.add_argument("--run", type=int, default=30, help="run sample count")
    parser.add_argument("--delay", type=float, default=0.2, help="delay between samples (s)")
    parser.add_argument("--gap", type=float, default=0.0, help="delay between baseline and run (s)")
    parser.add_argument("--threshold", type=float, default=0.1, help="delta threshold (A)")
    parser.add_argument("--watch", action="store_true", help="repeat detection until interrupted")
    parser.add_argument("--cycles", type=int, default=0, help="number of watch cycles (0 = infinite)")
    parser.add_argument("--cycle-gap", type=float, default=1.0, help="delay between watch cycles (s)")
    args = parser.parse_args()

    if not args.watch:
        run_cycle(args, None)
        return

    cycle = 1
    while True:
        run_cycle(args, cycle)
        cycle += 1
        if args.cycles > 0 and cycle > args.cycles:
            break
        if args.cycle_gap > 0:
            time.sleep(args.cycle_gap)


if __name__ == "__main__":
    main()
