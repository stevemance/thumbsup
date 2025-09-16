#!/usr/bin/env python3
"""
Serial monitor for ThumbsUp Robot debugging
Connects to the Pico's USB serial output to display debug messages
"""

import serial
import serial.tools.list_ports
import sys
import time
import argparse
from datetime import datetime

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def find_pico_port():
    """Find the Raspberry Pi Pico serial port automatically"""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        # Check for Pico identifiers
        if "2E8A:0005" in port.hwid:  # Raspberry Pi Pico vendor/product ID
            return port.device
        if "Pico" in port.description:
            return port.device

    return None

def format_message(msg, timestamp=True):
    """Format and colorize debug messages"""
    if timestamp:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        msg = f"[{ts}] {msg}"

    # Colorize based on content
    if "ERROR" in msg or "FAIL" in msg:
        return f"{Colors.RED}{msg}{Colors.ENDC}"
    elif "WARNING" in msg or "WARN" in msg:
        return f"{Colors.YELLOW}{msg}{Colors.ENDC}"
    elif "SUCCESS" in msg or "OK" in msg:
        return f"{Colors.GREEN}{msg}{Colors.ENDC}"
    elif "STATUS" in msg:
        return f"{Colors.CYAN}{msg}{Colors.ENDC}"
    elif "ARMED" in msg:
        return f"{Colors.RED}{Colors.BOLD}{msg}{Colors.ENDC}"
    elif "Connected" in msg or "Bluetooth" in msg:
        return f"{Colors.BLUE}{msg}{Colors.ENDC}"

    return msg

def monitor_serial(port, baudrate=115200, raw=False):
    """Monitor serial output from the Pico"""
    try:
        ser = serial.Serial(port, baudrate, timeout=0.1)
        print(f"{Colors.GREEN}Connected to {port} at {baudrate} baud{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*50}{Colors.ENDC}")
        print(f"{Colors.CYAN}  ThumbsUp Robot Serial Monitor{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*50}{Colors.ENDC}\n")

        # Clear any buffered data
        ser.reset_input_buffer()

        while True:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline()
                    try:
                        # Try to decode as UTF-8
                        text = line.decode('utf-8').rstrip()
                        if text:
                            if raw:
                                print(text)
                            else:
                                print(format_message(text))
                    except UnicodeDecodeError:
                        # Print raw hex if decode fails
                        print(f"[RAW] {line.hex()}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"{Colors.RED}Read error: {e}{Colors.ENDC}")
                time.sleep(0.1)

    except serial.SerialException as e:
        print(f"{Colors.RED}Failed to open port {port}: {e}{Colors.ENDC}")
        return False

    finally:
        if 'ser' in locals():
            ser.close()
            print(f"\n{Colors.YELLOW}Serial port closed{Colors.ENDC}")

    return True

def list_ports():
    """List all available serial ports"""
    ports = serial.tools.list_ports.comports()

    if not ports:
        print(f"{Colors.YELLOW}No serial ports found{Colors.ENDC}")
        return

    print(f"{Colors.CYAN}Available serial ports:{Colors.ENDC}")
    for port in ports:
        info = f"  {port.device}"
        if port.description:
            info += f" - {port.description}"
        if port.hwid:
            info += f" [{port.hwid}]"

        # Highlight if it's a Pico
        if "2E8A:0005" in port.hwid or "Pico" in port.description:
            print(f"{Colors.GREEN}{info} <- Pico detected{Colors.ENDC}")
        else:
            print(info)

def main():
    parser = argparse.ArgumentParser(description='Serial monitor for ThumbsUp Robot')
    parser.add_argument('-p', '--port', type=str, help='Serial port (e.g., /dev/ttyACM0 or COM3)')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('-l', '--list', action='store_true', help='List available serial ports')
    parser.add_argument('-r', '--raw', action='store_true', help='Show raw output without formatting')
    parser.add_argument('-a', '--auto', action='store_true', help='Auto-detect and connect to Pico')

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    # Determine port to use
    port = args.port

    if not port:
        if args.auto:
            print(f"{Colors.YELLOW}Auto-detecting Pico...{Colors.ENDC}")
            port = find_pico_port()
            if port:
                print(f"{Colors.GREEN}Found Pico on {port}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Could not find Pico automatically{Colors.ENDC}")
                print("Available ports:")
                list_ports()
                sys.exit(1)
        else:
            # Try to auto-detect anyway
            port = find_pico_port()
            if port:
                print(f"{Colors.GREEN}Auto-detected Pico on {port}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}No port specified and could not auto-detect Pico{Colors.ENDC}")
                print("\nUsage examples:")
                print("  ./monitor.py --auto              # Auto-detect Pico")
                print("  ./monitor.py -p /dev/ttyACM0     # Linux")
                print("  ./monitor.py -p COM3             # Windows")
                print("  ./monitor.py --list              # List ports")
                sys.exit(1)

    # Start monitoring
    try:
        if not monitor_serial(port, args.baud, args.raw):
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Monitoring stopped by user{Colors.ENDC}")

if __name__ == "__main__":
    main()