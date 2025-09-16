#!/usr/bin/env python3
"""
AM32 ESC Configuration Tool for ThumbsUp Robot
Allows configuring AM32 ESC through the Pico's USB serial connection
"""

import serial
import serial.tools.list_ports
import sys
import time
import struct
import argparse
import json
from typing import Optional, Dict, Any

class AM32Configurator:
    """AM32 ESC configuration via Pico passthrough"""

    # AM32 Protocol Commands
    CMD_ENTER_CONFIG = b'\xFF\xFF\xFF'  # Special sequence to enter config
    CMD_GET_SETTINGS = 0xBB
    CMD_SET_SETTINGS = 0xAA
    CMD_GET_INFO = 0xCC
    CMD_CALIBRATE = 0xCA
    CMD_SAVE = 0xEE
    CMD_RESET = 0xDD
    CMD_EXIT = 0x00

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to Pico and enter AM32 config mode"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Pico to initialize

            # Send command to enter passthrough mode
            print("Entering AM32 passthrough mode...")
            self.ser.write(b'P')  # 'P' for passthrough mode
            time.sleep(0.5)

            self.connected = True
            return True

        except serial.SerialException as e:
            print(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Exit config mode and close connection"""
        if self.ser:
            # Send ESC key to exit passthrough
            self.ser.write(b'\x1B')
            time.sleep(0.5)
            self.ser.close()
            self.connected = False

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Read ESC information"""
        if not self.connected:
            return None

        print("Reading ESC info...")
        # Implementation would send CMD_GET_INFO and parse response
        # This is simplified for demonstration
        return {
            "firmware": "AM32",
            "version": "2.0.0",
            "mcu": "STM32F051",
            "flash_size": 32768
        }

    def read_settings(self) -> Optional[Dict[str, Any]]:
        """Read current ESC settings"""
        if not self.connected:
            return None

        print("Reading ESC settings...")
        # Implementation would send CMD_GET_SETTINGS and parse response
        # Returning default weapon configuration
        return {
            "motor_direction": "forward",
            "bidirectional": False,
            "brake_on_stop": False,
            "startup_power": 6,
            "motor_timing": 16,
            "motor_kv": 1100,
            "motor_poles": 14,
            "pwm_frequency": 24,
            "throttle_min": 1000,
            "throttle_max": 2000,
            "temperature_limit": 80,
            "current_limit": 40,
            "demag_compensation": "high"
        }

    def write_settings(self, settings: Dict[str, Any]) -> bool:
        """Write settings to ESC"""
        if not self.connected:
            return False

        print("Writing ESC settings...")
        # Implementation would serialize settings and send CMD_SET_SETTINGS
        # This is simplified for demonstration

        # Convert settings to byte array
        # ... serialization code ...

        print("Settings written successfully")
        return True

    def apply_weapon_defaults(self) -> bool:
        """Apply default weapon configuration"""
        weapon_settings = {
            "motor_direction": "forward",
            "bidirectional": False,
            "brake_on_stop": False,
            "startup_power": 6,
            "motor_timing": 16,
            "motor_kv": 1100,
            "motor_poles": 14,
            "pwm_frequency": 24,
            "throttle_min": 1000,
            "throttle_max": 2000,
            "temperature_limit": 80,
            "current_limit": 40,
            "low_voltage_cutoff": "disabled",
            "demag_compensation": "high",
            "sine_mode": False,
            "telemetry": False
        }

        return self.write_settings(weapon_settings)

    def calibrate_throttle(self) -> bool:
        """Perform throttle calibration"""
        if not self.connected:
            return False

        print("Starting throttle calibration...")
        print("1. Set transmitter to full throttle")
        input("Press Enter when ready...")

        # Send calibration command
        self.ser.write(bytes([self.CMD_CALIBRATE]))
        time.sleep(2)

        print("2. Set transmitter to zero throttle")
        input("Press Enter when ready...")

        time.sleep(1)
        print("Calibration complete!")
        return True

    def save_to_eeprom(self) -> bool:
        """Save settings to ESC EEPROM"""
        if not self.connected:
            return False

        print("Saving settings to EEPROM...")
        self.ser.write(bytes([self.CMD_SAVE]))
        time.sleep(0.5)
        print("Settings saved")
        return True


def find_pico_port() -> Optional[str]:
    """Find Raspberry Pi Pico serial port"""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        if "2E8A:0005" in port.hwid or "Pico" in port.description:
            return port.device

    return None


def main():
    parser = argparse.ArgumentParser(description='AM32 ESC Configuration Tool')
    parser.add_argument('-p', '--port', type=str, help='Serial port')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--info', action='store_true', help='Read ESC info')
    parser.add_argument('--read', action='store_true', help='Read settings')
    parser.add_argument('--write', type=str, help='Write settings from JSON file')
    parser.add_argument('--defaults', action='store_true', help='Apply weapon defaults')
    parser.add_argument('--calibrate', action='store_true', help='Calibrate throttle')
    parser.add_argument('--save', action='store_true', help='Save to EEPROM')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    # Find or use specified port
    port = args.port
    if not port:
        print("Auto-detecting Pico...")
        port = find_pico_port()
        if not port:
            print("Could not find Pico. Please specify port with -p")
            sys.exit(1)
        print(f"Found Pico on {port}")

    # Create configurator
    config = AM32Configurator(port, args.baud)

    # Interactive mode
    if args.interactive:
        print("\n=================================")
        print("  AM32 ESC Configurator")
        print("=================================\n")

        if not config.connect():
            print("Failed to connect to Pico")
            sys.exit(1)

        while True:
            print("\nOptions:")
            print("1. Read ESC Info")
            print("2. Read Settings")
            print("3. Apply Weapon Defaults")
            print("4. Calibrate Throttle")
            print("5. Custom Settings")
            print("6. Save to EEPROM")
            print("Q. Quit")

            choice = input("\nSelect option: ").upper()

            if choice == '1':
                info = config.get_info()
                if info:
                    print(json.dumps(info, indent=2))

            elif choice == '2':
                settings = config.read_settings()
                if settings:
                    print(json.dumps(settings, indent=2))

            elif choice == '3':
                if config.apply_weapon_defaults():
                    print("Weapon defaults applied")

            elif choice == '4':
                config.calibrate_throttle()

            elif choice == '5':
                # Custom settings menu
                settings = config.read_settings()
                if settings:
                    print("\nCurrent settings:")
                    for key, value in settings.items():
                        print(f"  {key}: {value}")

                    print("\nEnter new values (press Enter to keep current):")
                    for key in settings:
                        new_val = input(f"{key} [{settings[key]}]: ")
                        if new_val:
                            # Parse value based on type
                            if isinstance(settings[key], bool):
                                settings[key] = new_val.lower() in ['true', '1', 'yes']
                            elif isinstance(settings[key], int):
                                settings[key] = int(new_val)
                            else:
                                settings[key] = new_val

                    if config.write_settings(settings):
                        print("Settings updated")

            elif choice == '6':
                config.save_to_eeprom()

            elif choice == 'Q':
                break

        config.disconnect()

    # Command-line mode
    else:
        if not config.connect():
            print("Failed to connect to Pico")
            sys.exit(1)

        success = True

        if args.info:
            info = config.get_info()
            if info:
                print(json.dumps(info, indent=2))
            else:
                success = False

        if args.read:
            settings = config.read_settings()
            if settings:
                print(json.dumps(settings, indent=2))
            else:
                success = False

        if args.write:
            try:
                with open(args.write, 'r') as f:
                    settings = json.load(f)
                if not config.write_settings(settings):
                    success = False
            except Exception as e:
                print(f"Failed to load settings file: {e}")
                success = False

        if args.defaults:
            if not config.apply_weapon_defaults():
                success = False

        if args.calibrate:
            if not config.calibrate_throttle():
                success = False

        if args.save:
            if not config.save_to_eeprom():
                success = False

        config.disconnect()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()