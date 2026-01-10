#!/usr/bin/env python3
"""
AM32 ESC Configuration Generator

Converts YAML config to binary and C header for embedding in firmware.

Usage:
    python tools/am32_config_gen.py config/am32_config.yaml

Outputs:
    build/am32_config.bin       - Raw 192-byte binary
    build/am32_config_data.h    - C header with byte array
"""

import sys
import os
import yaml
from pathlib import Path

# EEPROM size
EEPROM_SIZE = 192

# Field offsets (must match am32_bootloader.h)
OFFSETS = {
    'reserved_0': 0,
    'eeprom_version': 1,
    'reserved_1': 2,
    'fw_version_major': 3,
    'fw_version_minor': 4,
    'max_ramp': 5,
    'min_duty_cycle': 6,
    'disable_stick_cal': 7,
    'abs_voltage_cutoff': 8,
    'current_p': 9,
    'current_i': 10,
    'current_d': 11,
    'active_brake_power': 12,
    # 13-16 reserved
    'dir_reversed': 17,
    'bidirectional': 18,
    'use_sine_start': 19,
    'comp_pwm': 20,
    'variable_pwm': 21,
    'stuck_rotor_prot': 22,
    'advance_level': 23,
    'pwm_frequency': 24,
    'startup_power': 25,
    'motor_kv': 26,
    'motor_poles': 27,
    'brake_on_stop': 28,
    'stall_protection': 29,
    'beep_volume': 30,
    'telemetry_interval': 31,
    'servo_low': 32,
    'servo_high': 33,
    'servo_neutral': 34,
    'servo_deadband': 35,
    'low_voltage_cutoff': 36,
    'low_cell_volt_cutoff': 37,
    'rc_car_reverse': 38,
    'use_hall_sensors': 39,
    'sine_changeover': 40,
    'drag_brake_strength': 41,
    'driving_brake_strength': 42,
    'temp_limit': 43,
    'current_limit': 44,
    'sine_mode_power': 45,
    'input_type': 46,
    'auto_advance': 47,
    # 48-175: tune array (128 bytes)
    'can_node': 176,
    'esc_index': 177,
    'require_arming': 178,
    'telem_rate': 179,
    'require_zero_throttle': 180,
    'filter_hz': 181,
    'debug_rate': 182,
    'term_enable': 183,
    # 184-191 reserved
}


def bool_to_byte(val):
    """Convert bool/int to byte value."""
    if isinstance(val, bool):
        return 1 if val else 0
    return int(val) & 0xFF


def generate_config(yaml_path):
    """Generate 192-byte config from YAML file."""

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize buffer with 0xFF (matches erased flash state)
    buffer = bytearray([0xFF] * EEPROM_SIZE)

    # System info
    buffer[OFFSETS['eeprom_version']] = config.get('eeprom_version', 3)
    buffer[OFFSETS['fw_version_major']] = config.get('firmware_version', {}).get('major', 2)
    buffer[OFFSETS['fw_version_minor']] = config.get('firmware_version', {}).get('minor', 19)

    # Motor settings
    motor = config.get('motor', {})
    buffer[OFFSETS['motor_kv']] = motor.get('kv', 27)
    buffer[OFFSETS['motor_poles']] = motor.get('poles', 14)
    buffer[OFFSETS['dir_reversed']] = bool_to_byte(motor.get('direction_reversed', False))
    buffer[OFFSETS['bidirectional']] = bool_to_byte(motor.get('bidirectional', False))
    buffer[OFFSETS['brake_on_stop']] = bool_to_byte(motor.get('brake_on_stop', True))
    buffer[OFFSETS['stall_protection']] = bool_to_byte(motor.get('stall_protection', True))

    # Startup settings
    startup = config.get('startup', {})
    buffer[OFFSETS['startup_power']] = startup.get('power', 5)
    buffer[OFFSETS['use_sine_start']] = bool_to_byte(startup.get('use_sine_start', False))
    buffer[OFFSETS['sine_mode_power']] = startup.get('sine_mode_power', 6)
    buffer[OFFSETS['sine_changeover']] = startup.get('sine_changeover_throttle', 5)

    # Timing and PWM
    timing = config.get('timing', {})
    buffer[OFFSETS['advance_level']] = timing.get('advance_level', 16)
    buffer[OFFSETS['auto_advance']] = bool_to_byte(timing.get('auto_advance', False))
    buffer[OFFSETS['pwm_frequency']] = timing.get('pwm_frequency', 24)
    buffer[OFFSETS['comp_pwm']] = bool_to_byte(timing.get('comp_pwm', True))
    buffer[OFFSETS['variable_pwm']] = bool_to_byte(timing.get('variable_pwm', False))

    # Input settings
    input_cfg = config.get('input', {})
    buffer[OFFSETS['input_type']] = input_cfg.get('type', 0)
    buffer[OFFSETS['servo_low']] = input_cfg.get('servo_low', 128)
    buffer[OFFSETS['servo_high']] = input_cfg.get('servo_high', 128)
    buffer[OFFSETS['servo_neutral']] = input_cfg.get('servo_neutral', 128)
    buffer[OFFSETS['servo_deadband']] = input_cfg.get('servo_deadband', 5)
    buffer[OFFSETS['disable_stick_cal']] = bool_to_byte(input_cfg.get('disable_stick_calibration', False))

    # Braking settings
    braking = config.get('braking', {})
    buffer[OFFSETS['active_brake_power']] = braking.get('active_brake_power', 1)
    buffer[OFFSETS['drag_brake_strength']] = braking.get('drag_brake_strength', 0)
    buffer[OFFSETS['driving_brake_strength']] = braking.get('driving_brake_strength', 0)
    buffer[OFFSETS['rc_car_reverse']] = bool_to_byte(braking.get('rc_car_reverse', False))

    # Protection settings
    protection = config.get('protection', {})
    buffer[OFFSETS['temp_limit']] = protection.get('temperature_limit', 70)
    buffer[OFFSETS['current_limit']] = protection.get('current_limit', 10)
    buffer[OFFSETS['low_voltage_cutoff']] = bool_to_byte(protection.get('low_voltage_cutoff', False))
    buffer[OFFSETS['low_cell_volt_cutoff']] = protection.get('low_cell_volt_cutoff', 0)
    buffer[OFFSETS['abs_voltage_cutoff']] = protection.get('abs_voltage_cutoff', 0)
    buffer[OFFSETS['stuck_rotor_prot']] = bool_to_byte(protection.get('stuck_rotor_protection', True))

    # Current control
    current = config.get('current_control', {})
    buffer[OFFSETS['current_p']] = current.get('p_gain', 0)
    buffer[OFFSETS['current_i']] = current.get('i_gain', 0)
    buffer[OFFSETS['current_d']] = current.get('d_gain', 0)
    buffer[OFFSETS['max_ramp']] = current.get('max_ramp', 10)
    buffer[OFFSETS['min_duty_cycle']] = current.get('min_duty_cycle', 0)

    # Misc settings
    misc = config.get('misc', {})
    buffer[OFFSETS['beep_volume']] = misc.get('beep_volume', 5)
    buffer[OFFSETS['telemetry_interval']] = misc.get('telemetry_interval', 0)
    buffer[OFFSETS['use_hall_sensors']] = bool_to_byte(misc.get('use_hall_sensors', False))

    # CAN settings
    can = config.get('can', {})
    buffer[OFFSETS['can_node']] = can.get('node', 0)
    buffer[OFFSETS['esc_index']] = can.get('esc_index', 0)
    buffer[OFFSETS['require_arming']] = bool_to_byte(can.get('require_arming', False))
    buffer[OFFSETS['telem_rate']] = can.get('telem_rate', 0)
    buffer[OFFSETS['require_zero_throttle']] = bool_to_byte(can.get('require_zero_throttle', False))
    buffer[OFFSETS['filter_hz']] = can.get('filter_hz', 0)
    buffer[OFFSETS['debug_rate']] = can.get('debug_rate', 0)
    buffer[OFFSETS['term_enable']] = bool_to_byte(can.get('term_enable', False))

    # Tune array (128 bytes at offset 48)
    tune = config.get('tune_array', [0] * 128)
    for i, val in enumerate(tune[:128]):
        buffer[48 + i] = int(val) & 0xFF

    return buffer


def write_binary(buffer, output_path):
    """Write raw binary file."""
    with open(output_path, 'wb') as f:
        f.write(buffer)
    print(f"Generated: {output_path}")


def write_c_header(buffer, output_path):
    """Write C header with byte array."""

    header = """/**
 * AM32 ESC Configuration Data
 *
 * Auto-generated from config/am32_config.yaml
 * DO NOT EDIT - modify the YAML file instead
 */

#ifndef AM32_CONFIG_DATA_H
#define AM32_CONFIG_DATA_H

#include <stdint.h>

#define AM32_CONFIG_SIZE 192

static const uint8_t am32_desired_config[AM32_CONFIG_SIZE] = {
"""

    # Format bytes in rows of 16
    lines = []
    for i in range(0, len(buffer), 16):
        row = buffer[i:i+16]
        hex_vals = ', '.join(f'0x{b:02X}' for b in row)
        lines.append(f'    {hex_vals}')

    header += ',\n'.join(lines)
    header += '\n};\n\n#endif // AM32_CONFIG_DATA_H\n'

    with open(output_path, 'w') as f:
        f.write(header)
    print(f"Generated: {output_path}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config.yaml>")
        print(f"Example: {sys.argv[0]} config/am32_config.yaml")
        sys.exit(1)

    yaml_path = sys.argv[1]

    if not os.path.exists(yaml_path):
        print(f"Error: Config file not found: {yaml_path}")
        sys.exit(1)

    # Determine output directory
    script_dir = Path(__file__).parent.parent
    build_dir = script_dir / 'build'
    build_dir.mkdir(exist_ok=True)

    # Generate config
    print(f"Reading: {yaml_path}")
    buffer = generate_config(yaml_path)

    # Write outputs
    write_binary(buffer, build_dir / 'am32_config.bin')
    write_c_header(buffer, build_dir / 'am32_config_data.h')

    print(f"\nGenerated {len(buffer)} byte configuration")


if __name__ == '__main__':
    main()
