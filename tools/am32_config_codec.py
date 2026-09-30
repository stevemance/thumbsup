#!/usr/bin/env python3
"""AM32 config codec.

Converts AM32 192-byte EEPROM images between:
- human-editable YAML
- binary (.bin)
- hex text (.hexcfg)

The field mapping matches the AM32 offsets used by this repository.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Any

import yaml

EEPROM_SIZE = 192

OFF = {
    "reserved_0": 0,
    "eeprom_version": 1,
    "reserved_1": 2,
    "fw_version_major": 3,
    "fw_version_minor": 4,
    "max_ramp": 5,
    "min_duty_cycle": 6,
    "disable_stick_cal": 7,
    "abs_voltage_cutoff": 8,
    "current_p": 9,
    "current_i": 10,
    "current_d": 11,
    "active_brake_power": 12,
    "reserved_3_start": 13,  # 13..16
    "dir_reversed": 17,
    "bidirectional": 18,
    "use_sine_start": 19,
    "comp_pwm": 20,
    "variable_pwm": 21,
    "stuck_rotor_prot": 22,
    "advance_level": 23,
    "pwm_frequency": 24,
    "startup_power": 25,
    "motor_kv": 26,
    "motor_poles": 27,
    "brake_on_stop": 28,
    "stall_protection": 29,
    "beep_volume": 30,
    "telemetry_interval": 31,
    "servo_low": 32,
    "servo_high": 33,
    "servo_neutral": 34,
    "servo_deadband": 35,
    "low_voltage_cutoff": 36,
    "low_cell_volt_cutoff": 37,
    "rc_car_reverse": 38,
    "use_hall_sensors": 39,
    "sine_changeover": 40,
    "drag_brake_strength": 41,
    "driving_brake_strength": 42,
    "temp_limit": 43,
    "current_limit": 44,
    "sine_mode_power": 45,
    "input_type": 46,
    "auto_advance": 47,
    "tune_start": 48,         # 48..175
    "can_node": 176,
    "esc_index": 177,
    "require_arming": 178,
    "telem_rate": 179,
    "require_zero_throttle": 180,
    "filter_hz": 181,
    "debug_rate": 182,
    "term_enable": 183,
    "reserved_tail_start": 184,  # 184..191
}


DEFAULT_YAML_TEMPLATE: dict[str, Any] = {
    "eeprom_version": 3,
    "firmware_version": {"major": 2, "minor": 19},
    "motor": {
        "kv": 27,
        "poles": 14,
        "direction_reversed": False,
        "bidirectional": False,
        "brake_on_stop": True,
        "stall_protection": True,
    },
    "startup": {
        "power": 5,
        "use_sine_start": False,
        "sine_mode_power": 6,
        "sine_changeover_throttle": 5,
    },
    "timing": {
        "advance_level": 16,
        "auto_advance": False,
        "pwm_frequency": 24,
        "comp_pwm": True,
        "variable_pwm": False,
    },
    "input": {
        "type": 0,
        "servo_low": 128,
        "servo_high": 128,
        "servo_neutral": 128,
        "servo_deadband": 5,
        "disable_stick_calibration": False,
    },
    "braking": {
        "active_brake_power": 1,
        "drag_brake_strength": 0,
        "driving_brake_strength": 0,
        "rc_car_reverse": False,
    },
    "protection": {
        "temperature_limit": 70,
        "current_limit": 10,
        "low_voltage_cutoff": False,
        "low_cell_volt_cutoff": 0,
        "abs_voltage_cutoff": 0,
        "stuck_rotor_protection": True,
    },
    "current_control": {
        "p_gain": 0,
        "i_gain": 0,
        "d_gain": 0,
        "max_ramp": 10,
        "min_duty_cycle": 0,
    },
    "misc": {
        "beep_volume": 5,
        "telemetry_interval": 0,
        "use_hall_sensors": False,
    },
    "can": {
        "node": 0,
        "esc_index": 0,
        "require_arming": False,
        "telem_rate": 0,
        "require_zero_throttle": False,
        "filter_hz": 0,
        "debug_rate": 0,
        "term_enable": False,
    },
    "tune_array": [0] * 128,
    "raw": {
        "reserved_0": 0xFF,
        "reserved_1": 0xFF,
        "reserved_3": [0xFF, 0xFF, 0xFF, 0xFF],
        "reserved_tail": [0xFF] * 8,
    },
}


def _as_u8(value: Any, name: str) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: expected integer-like value, got {value!r}") from exc
    if iv < 0 or iv > 255:
        raise ValueError(f"{name}: value {iv} out of range (0..255)")
    return iv


def _as_bool_byte(value: Any, name: str) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    # Preserve non-boolean byte values (e.g. 0xFF) for round-trip fidelity.
    return _as_u8(value, name)


def _decode_boolish(byte_val: int) -> bool | int:
    if byte_val == 0:
        return False
    if byte_val == 1:
        return True
    return byte_val


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: YAML top-level must be a mapping/object")
    return data


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    return _read_yaml(path)


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _parse_image(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) == EEPROM_SIZE:
        return raw

    text = path.read_text(encoding="utf-8")
    parts: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            parts.append(line)
    hex_text = "".join(parts)

    if len(hex_text) != EEPROM_SIZE * 2:
        raise ValueError(
            f"{path}: expected {EEPROM_SIZE} bytes or {EEPROM_SIZE * 2} hex chars, got {len(raw)} bytes / {len(hex_text)} hex chars"
        )
    if re.search(r"[^0-9a-fA-F]", hex_text):
        raise ValueError(f"{path}: non-hex characters found in text image")
    return bytes.fromhex(hex_text)


def parse_image(path: Path) -> bytes:
    return _parse_image(path)


def _write_bin(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _write_hexcfg(path: Path, data: bytes, bytes_per_line: int = 48) -> None:
    lines: list[str] = []
    for i in range(0, len(data), bytes_per_line):
        lines.append(data[i:i + bytes_per_line].hex())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _encode_yaml_to_image(payload: dict[str, Any]) -> bytes:
    merged = _merge(DEFAULT_YAML_TEMPLATE, payload)
    b = bytearray([0xFF] * EEPROM_SIZE)

    # raw/reserved bytes for round-trip stability
    raw_cfg = merged.get("raw", {}) or {}
    if not isinstance(raw_cfg, dict):
        raise ValueError("raw must be a mapping/object when provided")
    b[OFF["reserved_0"]] = _as_u8(raw_cfg.get("reserved_0", 0xFF), "raw.reserved_0")
    b[OFF["reserved_1"]] = _as_u8(raw_cfg.get("reserved_1", 0xFF), "raw.reserved_1")
    r3 = raw_cfg.get("reserved_3", [0xFF, 0xFF, 0xFF, 0xFF])
    if not isinstance(r3, list) or len(r3) != 4:
        raise ValueError("raw.reserved_3 must be a list of 4 bytes")
    for i, v in enumerate(r3):
        b[OFF["reserved_3_start"] + i] = _as_u8(v, f"raw.reserved_3[{i}]")
    rt = raw_cfg.get("reserved_tail", [0xFF] * 8)
    if not isinstance(rt, list) or len(rt) != 8:
        raise ValueError("raw.reserved_tail must be a list of 8 bytes")
    for i, v in enumerate(rt):
        b[OFF["reserved_tail_start"] + i] = _as_u8(v, f"raw.reserved_tail[{i}]")

    b[OFF["eeprom_version"]] = _as_u8(merged.get("eeprom_version", 3), "eeprom_version")

    fw = merged.get("firmware_version", {}) or {}
    b[OFF["fw_version_major"]] = _as_u8(fw.get("major", 2), "firmware_version.major")
    b[OFF["fw_version_minor"]] = _as_u8(fw.get("minor", 19), "firmware_version.minor")

    motor = merged.get("motor", {}) or {}
    b[OFF["motor_kv"]] = _as_u8(motor.get("kv", 27), "motor.kv")
    b[OFF["motor_poles"]] = _as_u8(motor.get("poles", 14), "motor.poles")
    b[OFF["dir_reversed"]] = _as_bool_byte(motor.get("direction_reversed", False), "motor.direction_reversed")
    b[OFF["bidirectional"]] = _as_bool_byte(motor.get("bidirectional", False), "motor.bidirectional")
    b[OFF["brake_on_stop"]] = _as_bool_byte(motor.get("brake_on_stop", True), "motor.brake_on_stop")
    b[OFF["stall_protection"]] = _as_bool_byte(motor.get("stall_protection", True), "motor.stall_protection")

    startup = merged.get("startup", {}) or {}
    b[OFF["startup_power"]] = _as_u8(startup.get("power", 5), "startup.power")
    b[OFF["use_sine_start"]] = _as_bool_byte(startup.get("use_sine_start", False), "startup.use_sine_start")
    b[OFF["sine_mode_power"]] = _as_u8(startup.get("sine_mode_power", 6), "startup.sine_mode_power")
    b[OFF["sine_changeover"]] = _as_u8(startup.get("sine_changeover_throttle", 5), "startup.sine_changeover_throttle")

    timing = merged.get("timing", {}) or {}
    b[OFF["advance_level"]] = _as_u8(timing.get("advance_level", 16), "timing.advance_level")
    b[OFF["auto_advance"]] = _as_bool_byte(timing.get("auto_advance", False), "timing.auto_advance")
    b[OFF["pwm_frequency"]] = _as_u8(timing.get("pwm_frequency", 24), "timing.pwm_frequency")
    b[OFF["comp_pwm"]] = _as_bool_byte(timing.get("comp_pwm", True), "timing.comp_pwm")
    b[OFF["variable_pwm"]] = _as_bool_byte(timing.get("variable_pwm", False), "timing.variable_pwm")

    input_cfg = merged.get("input", {}) or {}
    b[OFF["input_type"]] = _as_u8(input_cfg.get("type", 0), "input.type")
    b[OFF["servo_low"]] = _as_u8(input_cfg.get("servo_low", 128), "input.servo_low")
    b[OFF["servo_high"]] = _as_u8(input_cfg.get("servo_high", 128), "input.servo_high")
    b[OFF["servo_neutral"]] = _as_u8(input_cfg.get("servo_neutral", 128), "input.servo_neutral")
    b[OFF["servo_deadband"]] = _as_u8(input_cfg.get("servo_deadband", 5), "input.servo_deadband")
    b[OFF["disable_stick_cal"]] = _as_bool_byte(
        input_cfg.get("disable_stick_calibration", False),
        "input.disable_stick_calibration",
    )

    braking = merged.get("braking", {}) or {}
    b[OFF["active_brake_power"]] = _as_u8(braking.get("active_brake_power", 1), "braking.active_brake_power")
    b[OFF["drag_brake_strength"]] = _as_u8(braking.get("drag_brake_strength", 0), "braking.drag_brake_strength")
    b[OFF["driving_brake_strength"]] = _as_u8(braking.get("driving_brake_strength", 0), "braking.driving_brake_strength")
    b[OFF["rc_car_reverse"]] = _as_bool_byte(braking.get("rc_car_reverse", False), "braking.rc_car_reverse")

    prot = merged.get("protection", {}) or {}
    b[OFF["temp_limit"]] = _as_u8(prot.get("temperature_limit", 70), "protection.temperature_limit")
    b[OFF["current_limit"]] = _as_u8(prot.get("current_limit", 10), "protection.current_limit")
    b[OFF["low_voltage_cutoff"]] = _as_bool_byte(prot.get("low_voltage_cutoff", False), "protection.low_voltage_cutoff")
    b[OFF["low_cell_volt_cutoff"]] = _as_u8(prot.get("low_cell_volt_cutoff", 0), "protection.low_cell_volt_cutoff")
    b[OFF["abs_voltage_cutoff"]] = _as_u8(prot.get("abs_voltage_cutoff", 0), "protection.abs_voltage_cutoff")
    b[OFF["stuck_rotor_prot"]] = _as_bool_byte(prot.get("stuck_rotor_protection", True), "protection.stuck_rotor_protection")

    cc = merged.get("current_control", {}) or {}
    b[OFF["current_p"]] = _as_u8(cc.get("p_gain", 0), "current_control.p_gain")
    b[OFF["current_i"]] = _as_u8(cc.get("i_gain", 0), "current_control.i_gain")
    b[OFF["current_d"]] = _as_u8(cc.get("d_gain", 0), "current_control.d_gain")
    b[OFF["max_ramp"]] = _as_u8(cc.get("max_ramp", 10), "current_control.max_ramp")
    b[OFF["min_duty_cycle"]] = _as_u8(cc.get("min_duty_cycle", 0), "current_control.min_duty_cycle")

    misc = merged.get("misc", {}) or {}
    b[OFF["beep_volume"]] = _as_u8(misc.get("beep_volume", 5), "misc.beep_volume")
    b[OFF["telemetry_interval"]] = _as_u8(misc.get("telemetry_interval", 0), "misc.telemetry_interval")
    b[OFF["use_hall_sensors"]] = _as_bool_byte(misc.get("use_hall_sensors", False), "misc.use_hall_sensors")

    can = merged.get("can", {}) or {}
    b[OFF["can_node"]] = _as_u8(can.get("node", 0), "can.node")
    b[OFF["esc_index"]] = _as_u8(can.get("esc_index", 0), "can.esc_index")
    b[OFF["require_arming"]] = _as_bool_byte(can.get("require_arming", False), "can.require_arming")
    b[OFF["telem_rate"]] = _as_u8(can.get("telem_rate", 0), "can.telem_rate")
    b[OFF["require_zero_throttle"]] = _as_bool_byte(can.get("require_zero_throttle", False), "can.require_zero_throttle")
    b[OFF["filter_hz"]] = _as_u8(can.get("filter_hz", 0), "can.filter_hz")
    b[OFF["debug_rate"]] = _as_u8(can.get("debug_rate", 0), "can.debug_rate")
    b[OFF["term_enable"]] = _as_bool_byte(can.get("term_enable", False), "can.term_enable")

    tune = merged.get("tune_array", [0] * 128)
    if not isinstance(tune, list) or len(tune) != 128:
        raise ValueError("tune_array must be a list of exactly 128 values")
    for i, v in enumerate(tune):
        b[OFF["tune_start"] + i] = _as_u8(v, f"tune_array[{i}]")

    return bytes(b)


def encode_yaml_to_image(payload: dict[str, Any]) -> bytes:
    return _encode_yaml_to_image(payload)


def _decode_image_to_yaml(data: bytes) -> dict[str, Any]:
    if len(data) != EEPROM_SIZE:
        raise ValueError(f"expected {EEPROM_SIZE} bytes, got {len(data)}")

    b = data
    payload: dict[str, Any] = {
        "eeprom_version": b[OFF["eeprom_version"]],
        "firmware_version": {
            "major": b[OFF["fw_version_major"]],
            "minor": b[OFF["fw_version_minor"]],
        },
        "motor": {
            "kv": b[OFF["motor_kv"]],
            "poles": b[OFF["motor_poles"]],
            "direction_reversed": _decode_boolish(b[OFF["dir_reversed"]]),
            "bidirectional": _decode_boolish(b[OFF["bidirectional"]]),
            "brake_on_stop": _decode_boolish(b[OFF["brake_on_stop"]]),
            "stall_protection": _decode_boolish(b[OFF["stall_protection"]]),
        },
        "startup": {
            "power": b[OFF["startup_power"]],
            "use_sine_start": _decode_boolish(b[OFF["use_sine_start"]]),
            "sine_mode_power": b[OFF["sine_mode_power"]],
            "sine_changeover_throttle": b[OFF["sine_changeover"]],
        },
        "timing": {
            "advance_level": b[OFF["advance_level"]],
            "auto_advance": _decode_boolish(b[OFF["auto_advance"]]),
            "pwm_frequency": b[OFF["pwm_frequency"]],
            "comp_pwm": _decode_boolish(b[OFF["comp_pwm"]]),
            "variable_pwm": _decode_boolish(b[OFF["variable_pwm"]]),
        },
        "input": {
            "type": b[OFF["input_type"]],
            "servo_low": b[OFF["servo_low"]],
            "servo_high": b[OFF["servo_high"]],
            "servo_neutral": b[OFF["servo_neutral"]],
            "servo_deadband": b[OFF["servo_deadband"]],
            "disable_stick_calibration": _decode_boolish(b[OFF["disable_stick_cal"]]),
        },
        "braking": {
            "active_brake_power": b[OFF["active_brake_power"]],
            "drag_brake_strength": b[OFF["drag_brake_strength"]],
            "driving_brake_strength": b[OFF["driving_brake_strength"]],
            "rc_car_reverse": _decode_boolish(b[OFF["rc_car_reverse"]]),
        },
        "protection": {
            "temperature_limit": b[OFF["temp_limit"]],
            "current_limit": b[OFF["current_limit"]],
            "low_voltage_cutoff": _decode_boolish(b[OFF["low_voltage_cutoff"]]),
            "low_cell_volt_cutoff": b[OFF["low_cell_volt_cutoff"]],
            "abs_voltage_cutoff": b[OFF["abs_voltage_cutoff"]],
            "stuck_rotor_protection": _decode_boolish(b[OFF["stuck_rotor_prot"]]),
        },
        "current_control": {
            "p_gain": b[OFF["current_p"]],
            "i_gain": b[OFF["current_i"]],
            "d_gain": b[OFF["current_d"]],
            "max_ramp": b[OFF["max_ramp"]],
            "min_duty_cycle": b[OFF["min_duty_cycle"]],
        },
        "misc": {
            "beep_volume": b[OFF["beep_volume"]],
            "telemetry_interval": b[OFF["telemetry_interval"]],
            "use_hall_sensors": _decode_boolish(b[OFF["use_hall_sensors"]]),
        },
        "can": {
            "node": b[OFF["can_node"]],
            "esc_index": b[OFF["esc_index"]],
            "require_arming": _decode_boolish(b[OFF["require_arming"]]),
            "telem_rate": b[OFF["telem_rate"]],
            "require_zero_throttle": _decode_boolish(b[OFF["require_zero_throttle"]]),
            "filter_hz": b[OFF["filter_hz"]],
            "debug_rate": b[OFF["debug_rate"]],
            "term_enable": _decode_boolish(b[OFF["term_enable"]]),
        },
        "tune_array": [b[OFF["tune_start"] + i] for i in range(128)],
        "raw": {
            "reserved_0": b[OFF["reserved_0"]],
            "reserved_1": b[OFF["reserved_1"]],
            "reserved_3": [b[OFF["reserved_3_start"] + i] for i in range(4)],
            "reserved_tail": [b[OFF["reserved_tail_start"] + i] for i in range(8)],
        },
    }
    return payload


def decode_image_to_yaml(data: bytes) -> dict[str, Any]:
    return _decode_image_to_yaml(data)


def cmd_compile(args: argparse.Namespace) -> int:
    in_yaml = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()

    payload = load_yaml_mapping(in_yaml)
    image = encode_yaml_to_image(payload)

    fmt = args.format
    if fmt is None:
        if out.suffix.lower() == ".bin":
            fmt = "bin"
        else:
            fmt = "hex"

    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "bin":
        _write_bin(out, image)
    elif fmt == "hex":
        _write_hexcfg(out, image)
    else:
        raise ValueError(f"unsupported output format: {fmt}")

    print(f"Wrote {len(image)} bytes to {out} ({fmt})")
    return 0


def cmd_decompile(args: argparse.Namespace) -> int:
    in_path = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()

    image = parse_image(in_path)
    payload = decode_image_to_yaml(image)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    print(f"Wrote YAML to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AM32 config codec (yaml <-> hexcfg/bin)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile", help="compile YAML to AM32 image (.hexcfg or .bin)")
    c.add_argument("--input", required=True, help="input YAML file")
    c.add_argument("--output", required=True, help="output file (.hexcfg/.txt or .bin)")
    c.add_argument("--format", choices=["hex", "bin"], default=None, help="override output format")
    c.set_defaults(func=cmd_compile)

    d = sub.add_parser("decompile", help="decompile AM32 image (.hexcfg/.bin) to YAML")
    d.add_argument("--input", required=True, help="input .hexcfg/.txt/.bin")
    d.add_argument("--output", required=True, help="output YAML file")
    d.set_defaults(func=cmd_decompile)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
