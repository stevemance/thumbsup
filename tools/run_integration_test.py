#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None


DEFAULT_VOLTAGE = 12.6
DEFAULT_CURRENT = 3.0
DEFAULT_CHANNEL = 1
DEFAULT_PSU_INTERVAL_S = 0.5
DEFAULT_PROMPT_TIMEOUT_S = 5
DEFAULT_SERIAL_BAUD = 115200
DEFAULT_TEST_TIMEOUT_S = 240

DEFAULT_STEPS = [20, 35, 50, 65, 80]
DEFAULT_HOLD_S = 20
DEFAULT_COOLDOWN_S = 10
DEFAULT_ARM_S = 5


def run_cmd(args, check=True, capture_output=True):
    result = subprocess.run(
        args,
        capture_output=capture_output,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(args)}\n{detail}")
    return result


def ensure_pyserial():
    if serial is None:
        raise RuntimeError("pyserial not installed. Try: pip install pyserial")


def find_pico_port():
    ports = serial.tools.list_ports.comports()
    pico_ports = []
    for port in ports:
        if port.vid == 0x2E8A or (port.hwid and "2E8A" in port.hwid):
            pico_ports.append(port.device)
            continue
        if port.description and "Pico" in port.description:
            pico_ports.append(port.device)

    if pico_ports:
        return pico_ports[0]

    acm_ports = [p.device for p in ports if "ttyACM" in p.device]
    if len(acm_ports) == 1:
        return acm_ports[0]

    return None


def wait_for_port(timeout_s):
    start = time.time()
    while time.time() - start < timeout_s:
        port = find_pico_port()
        if port:
            return port
        time.sleep(0.5)
    return None


def build_firmware(repo_root):
    script = os.path.join(repo_root, "tools", "build.sh")
    run_cmd([script], check=True, capture_output=False)


def flash_firmware(uf2_path):
    if not os.path.exists(uf2_path):
        raise RuntimeError(f"firmware UF2 not found: {uf2_path}")

    run_cmd(["picotool", "reboot", "-f", "-u"], check=False)
    run_cmd(["picotool", "load", "-f", "-x", uf2_path], check=True)


def psu_set(channel, voltage, current):
    run_cmd([
        "labctl", "psu", "set",
        "--channel", str(channel),
        "--voltage", str(voltage),
        "--current", str(current),
        "--on",
    ], check=True)


def psu_off(channel):
    run_cmd(["labctl", "psu", "off", "--channel", str(channel)], check=False)


def start_psu_log(repo_root, channel, duration_s, interval_s, out_path):
    script = os.path.join(repo_root, "tools", "psu_log.py")
    return subprocess.Popen([
        sys.executable,
        script,
        "--channel", str(channel),
        "--duration", str(duration_s),
        "--interval", str(interval_s),
        "--out", out_path,
    ])


def send_trigger(ser, duration_s):
    start = time.time()
    while time.time() - start < duration_s:
        ser.write(b"I")
        ser.flush()
        time.sleep(0.2)

def run_serial_capture(port, baud, log_path, timeout_s, send_prompt,
                       psu_on_pattern=None, psu_on_callback=None):
    summary = {
        "telemetry": None,
        "rpm": None,
    }
    summary_seen = False
    last_output = time.time()
    psu_on_armed = psu_on_pattern is not None and psu_on_callback is not None

    telem_re = re.compile(r"Telemetry rate: (PASS|FAIL)")
    rpm_re = re.compile(r"RPM monotonicity: (PASS|FAIL)")

    with serial.Serial(port, baud, timeout=0.1) as ser, open(log_path, "w") as log:
        ser.reset_input_buffer()
        if send_prompt:
            send_trigger(ser, DEFAULT_PROMPT_TIMEOUT_S - 1)

        start = time.time()
        while time.time() - start < timeout_s:
            raw = ser.readline()
            if not raw:
                if summary_seen and (time.time() - last_output) > 2.0:
                    break
                continue

            line = raw.decode("utf-8", errors="replace").rstrip()
            last_output = time.time()

            print(line)
            log.write(line + "\n")
            log.flush()

            if psu_on_armed and psu_on_pattern in line:
                psu_on_callback()
                psu_on_armed = False

            if "Integration Summary" in line:
                summary_seen = True

            match = telem_re.search(line)
            if match:
                summary["telemetry"] = match.group(1)

            match = rpm_re.search(line)
            if match:
                summary["rpm"] = match.group(1)

            if summary["telemetry"] and summary["rpm"] and summary_seen:
                if (time.time() - last_output) > 1.0:
                    break

    return summary


def main():
    parser = argparse.ArgumentParser(description="Run the ThumbsUp integration test end-to-end.")
    parser.add_argument("--voltage", type=float, default=DEFAULT_VOLTAGE)
    parser.add_argument("--current", type=float, default=DEFAULT_CURRENT)
    parser.add_argument("--channel", type=int, default=DEFAULT_CHANNEL)
    parser.add_argument("--psu-interval", type=float, default=DEFAULT_PSU_INTERVAL_S)
    parser.add_argument("--port", type=str, default="")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--no-flash", action="store_true")
    parser.add_argument("--no-reboot", action="store_true")
    parser.add_argument("--no-psu", action="store_true")
    parser.add_argument("--psu-sync", dest="psu_sync", action="store_true", default=True,
                        help="Delay PSU power-on until the integration test arms")
    parser.add_argument("--no-psu-sync", dest="psu_sync", action="store_false",
                        help="Power PSU immediately instead of syncing to arming")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TEST_TIMEOUT_S)
    args = parser.parse_args()

    ensure_pyserial()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(repo_root, "integration_logs", f"run_{timestamp}")
    os.makedirs(log_dir, exist_ok=True)

    serial_log = os.path.join(log_dir, "serial.log")
    psu_log = os.path.join(log_dir, "psu_log.csv")

    expected_duration_s = DEFAULT_ARM_S + len(DEFAULT_STEPS) * (DEFAULT_HOLD_S + DEFAULT_COOLDOWN_S) + 20
    psu_duration_s = max(args.timeout, expected_duration_s)

    psu_proc = None
    psu_on = False
    try:
        if not args.no_build:
            build_firmware(repo_root)

        integration_uf2 = os.path.join(repo_root, "firmware", "build", "thumbsup_integration.uf2")
        default_uf2 = os.path.join(repo_root, "firmware", "build", "thumbsup.uf2")
        use_auto = os.path.exists(integration_uf2)
        uf2_path = integration_uf2 if use_auto else default_uf2

        if not args.no_flash:
            flash_firmware(uf2_path)

        if not args.no_psu:
            if args.psu_sync:
                psu_off(args.channel)
                psu_on = False
            else:
                psu_set(args.channel, args.voltage, args.current)
                psu_on = True
            psu_proc = start_psu_log(repo_root, args.channel, psu_duration_s, args.psu_interval, psu_log)

        if not args.no_reboot:
            run_cmd(["picotool", "reboot", "-f"], check=False)
            time.sleep(1.0)

        port = args.port
        if not port:
            port = wait_for_port(30)
        if not port:
            raise RuntimeError("could not find Pico serial port")

        print(f"Using serial port: {port}")
        def maybe_power_on():
            nonlocal psu_on
            if psu_on or args.no_psu:
                return
            psu_set(args.channel, args.voltage, args.current)
            psu_on = True

        psu_pattern = "DShot send throttle=" if (args.psu_sync and not args.no_psu) else None
        summary = run_serial_capture(
            port,
            DEFAULT_SERIAL_BAUD,
            serial_log,
            args.timeout,
            not use_auto,
            psu_on_pattern=psu_pattern,
            psu_on_callback=maybe_power_on,
        )

        print("\nIntegration test summary:")
        print(f"  Telemetry rate: {summary['telemetry'] or 'UNKNOWN'}")
        print(f"  RPM monotonicity: {summary['rpm'] or 'UNKNOWN'}")

        ok = summary["telemetry"] == "PASS" and summary["rpm"] == "PASS"
        sys.exit(0 if ok else 2)
    finally:
        if psu_proc and psu_proc.poll() is None:
            psu_proc.terminate()
        if not args.no_psu:
            psu_off(args.channel)


if __name__ == "__main__":
    main()
