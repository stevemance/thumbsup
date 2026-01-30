#!/usr/bin/env python3
import argparse
import time

import serial


def send_entry_pulses_low(ser, pulses, low_us, high_us):
    for _ in range(pulses):
        ser.break_condition = True
        time.sleep(low_us / 1e6)
        ser.break_condition = False
        time.sleep(high_us / 1e6)


def send_frame(ser, cmd, payload=b""):
    length = len(payload)
    checksum = cmd ^ (length & 0xFF) ^ ((length >> 8) & 0xFF)
    for b in payload:
        checksum ^= b
    frame = bytes([cmd, length & 0xFF, (length >> 8) & 0xFF]) + payload + bytes([checksum])
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    return frame


def read_response(ser, timeout_s):
    ser.timeout = timeout_s
    header = ser.read(2)
    if len(header) < 2:
        return None
    length = header[0] | (header[1] << 8)
    if length == 0:
        return b""
    data = ser.read(length)
    if len(data) != length:
        return None
    return data


def main():
    parser = argparse.ArgumentParser(description="Probe AM32 serial config over USB UART.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=19200, help="baud rate (default: 19200)")
    parser.add_argument("--entry-pulses", type=int, default=10, help="entry pulses (0 to skip)")
    parser.add_argument("--pulse-high-us", type=int, default=900, help="pulse high duration (us)")
    parser.add_argument("--pulse-low-us", type=int, default=100, help="pulse low duration (us)")
    parser.add_argument("--timeout", type=float, default=0.3, help="response timeout seconds")
    args = parser.parse_args()

    with serial.Serial(args.port, args.baud, timeout=args.timeout) as ser:
        print(f"Opened {args.port} @ {args.baud} baud")

        if args.entry_pulses > 0:
            print(f"Sending {args.entry_pulses} entry pulses (low {args.pulse_low_us}us, high {args.pulse_high_us}us)")
            send_entry_pulses_low(ser, args.entry_pulses, args.pulse_low_us, args.pulse_high_us)
            time.sleep(0.2)

        print("Sending KEEPALIVE...")
        send_frame(ser, 0xFF)
        resp = read_response(ser, args.timeout)
        print(f"KEEPALIVE response: {resp}")

        print("Sending GET_INFO...")
        send_frame(ser, 0xCC)
        resp = read_response(ser, args.timeout)
        print(f"GET_INFO response: {resp}")

        print("Sending GET_SETTINGS...")
        send_frame(ser, 0xBB)
        resp = read_response(ser, args.timeout)
        if resp is None:
            print("GET_SETTINGS response: None")
        else:
            print(f"GET_SETTINGS len={len(resp)}")
            print(resp)


if __name__ == "__main__":
    main()
