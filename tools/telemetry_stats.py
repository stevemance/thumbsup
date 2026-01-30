#!/usr/bin/env python3
import argparse
import re
import statistics
import sys


ERPM_RE = re.compile(r"EDT erpm:.*?erpm=(\d+)\s+rpm=(\d+)")
VOLT_RE = re.compile(r"EDT voltage:.*?voltage=([0-9.]+)V")
CURR_RE = re.compile(r"EDT current:.*?current=([0-9.]+)A")
TEMP_RE = re.compile(r"EDT temp:.*?temp=(\d+)C")
LAST_LINE_RE = re.compile(r"EDT last:")
LAST_ERPM_RE = re.compile(r"\berpm=(\d+)")
LAST_RPM_RE = re.compile(r"\brpm=(\d+)")
LAST_VOLT_RE = re.compile(r"V=([0-9.]+)")
LAST_CURR_RE = re.compile(r"I=([0-9.]+)")
LAST_TEMP_RE = re.compile(r"T=(\d+)")


def iter_lines(path):
    if path == "-":
        for line in sys.stdin:
            yield line
        return

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            yield line


def parse_values(lines, start_after=None, stop_after=None):
    values = {
        "erpm": [],
        "rpm": [],
        "voltage": [],
        "current": [],
        "temp": [],
    }
    started = start_after is None

    for line in lines:
        if not started:
            if start_after in line:
                started = True
            continue

        if stop_after and stop_after in line:
            break

        if LAST_LINE_RE.search(line):
            match = LAST_ERPM_RE.search(line)
            if match:
                values["erpm"].append(int(match.group(1)))
            match = LAST_RPM_RE.search(line)
            if match:
                values["rpm"].append(int(match.group(1)))
            match = LAST_VOLT_RE.search(line)
            if match:
                values["voltage"].append(float(match.group(1)))
            match = LAST_CURR_RE.search(line)
            if match:
                values["current"].append(float(match.group(1)))
            match = LAST_TEMP_RE.search(line)
            if match:
                values["temp"].append(int(match.group(1)))
            continue

        match = ERPM_RE.search(line)
        if match:
            values["erpm"].append(int(match.group(1)))
            values["rpm"].append(int(match.group(2)))
            continue

        match = VOLT_RE.search(line)
        if match:
            values["voltage"].append(float(match.group(1)))
            continue

        match = CURR_RE.search(line)
        if match:
            values["current"].append(float(match.group(1)))
            continue

        match = TEMP_RE.search(line)
        if match:
            values["temp"].append(int(match.group(1)))

    return values


def format_stats(label, samples, precision=None):
    if not samples:
        return f"{label}: no samples"

    samples = sorted(samples)
    median = statistics.median(samples)
    if precision is None:
        return (f"{label}: count={len(samples)} min={samples[0]} "
                f"median={int(median)} max={samples[-1]}")

    fmt = f"{{:.{precision}f}}"
    return (f"{label}: count={len(samples)} min={fmt.format(samples[0])} "
            f"median={fmt.format(median)} max={fmt.format(samples[-1])}")


def main():
    parser = argparse.ArgumentParser(description="Summarize EDT telemetry log values.")
    parser.add_argument("input", nargs="?", default="-",
                        help="log file to parse (default: stdin)")
    parser.add_argument("--start-after", help="start parsing after a line containing this text")
    parser.add_argument("--stop-after", help="stop parsing once a line containing this text appears")
    args = parser.parse_args()

    values = parse_values(iter_lines(args.input), args.start_after, args.stop_after)

    print(format_stats("erpm", values["erpm"]))
    print(format_stats("rpm", values["rpm"]))
    print(format_stats("voltage(V)", values["voltage"], precision=2))
    print(format_stats("current(A)", values["current"], precision=2))
    print(format_stats("temp(C)", values["temp"]))


if __name__ == "__main__":
    main()
