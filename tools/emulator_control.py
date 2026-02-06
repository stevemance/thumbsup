#!/usr/bin/env python3
"""Send scripted commands to the Pico W controller emulator over USB CDC."""

import argparse
import sys
import time
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    print(f"Missing pyserial: {exc}")
    sys.exit(1)


def find_pico_ports(product_hint=None):
    ports = serial.tools.list_ports.comports()
    matches = []
    for port in ports:
        if product_hint:
            product = (port.product or "").lower()
            description = (port.description or "").lower()
            if product_hint.lower() not in product and product_hint.lower() not in description:
                continue
        if "2E8A" in port.hwid or "Pico" in port.description or "RP2040" in port.description:
            matches.append(port.device)
    return matches


def resolve_port(args):
    if args.port:
        return args.port
    if not args.auto:
        return None
    matches = find_pico_ports(args.product)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    print("Multiple Pico devices found. Use --port to pick one:")
    for port in matches:
        print(f"  {port}")
    return None


def drain_serial(ser, max_time_s=0.05, max_lines=50):
    start = time.monotonic()
    lines = 0
    while (time.monotonic() - start) < max_time_s and lines < max_lines:
        raw = ser.readline()
        if not raw:
            return
        text = raw.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"RX {text}")
        lines += 1


def send_line(ser, line):
    ser.write((line + "\n").encode("utf-8"))
    print(f"TX {line}")


def run_script(ser, path, repeat):
    text = Path(path).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    for _ in range(repeat):
        for line in lines:
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0].upper() in {"SLEEP", "WAIT"}:
                if len(parts) != 2:
                    print(f"ERR invalid sleep: {line}")
                    continue
                try:
                    delay = float(parts[1])
                except ValueError:
                    print(f"ERR invalid sleep: {line}")
                    continue
                time.sleep(delay)
                drain_serial(ser)
                continue
            send_line(ser, line)
            drain_serial(ser)


def main():
    parser = argparse.ArgumentParser(description="Drive the HID emulator over USB serial.")
    parser.add_argument("--port", help="serial port (e.g. /dev/ttyACM0)")
    parser.add_argument("--auto", action="store_true", help="auto-detect Pico serial port")
    parser.add_argument("--product", help="substring to match USB product string")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud rate")
    parser.add_argument("--script", help="script file with commands")
    parser.add_argument("--repeat", type=int, default=1, help="repeat script")
    parser.add_argument("--command", help="send a single command")
    args = parser.parse_args()

    port = resolve_port(args)
    if not port:
        print("No serial port found. Use --port or --auto.")
        sys.exit(1)

    if not args.script and not args.command:
        print("Provide --script or --command.")
        sys.exit(1)

    with serial.Serial(port, args.baud, timeout=0.05, write_timeout=1.0) as ser:
        time.sleep(0.2)
        drain_serial(ser, max_time_s=0.2, max_lines=200)
        if args.command:
            send_line(ser, args.command)
            drain_serial(ser, max_time_s=0.2, max_lines=200)
        if args.script:
            run_script(ser, args.script, args.repeat)


if __name__ == "__main__":
    main()
