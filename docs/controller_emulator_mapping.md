# Controller Emulator Mapping

This document records the HID report fields the controller emulator will expose
and how Bluepad32 maps them into `uni_gamepad_t`.

## Goals

- Produce signed axes for drive/weapon inputs (Bluepad32 expects -512..511).
- Keep button usages aligned with Bluepad32's generic button map.
- Avoid RY pedal semantics (0..1023) for weapon control.

## Axis Mapping (Bluepad32)

Important: because the emulator uses VID/PID `0x2e8a/0x0001` (RP2040),
Bluepad32 does not find a device profile and currently falls back to the
**Android** HID parser.

Both the Android and generic parsers support a 2-stick mapping using:

- `X`  -> `gamepad.axis_x`  (left stick X, signed)
- `Y`  -> `gamepad.axis_y`  (left stick Y, signed)
- `Z`  -> `gamepad.axis_rx` (right stick X, signed)
- `RZ` -> `gamepad.axis_ry` (right stick Y, signed)

Note: Bluepad32 treats `RY` as a pedal in the generic parser. To keep weapon
control signed, we use `RZ` for the right-stick Y axis.

## D-Pad Mapping

- Use Hat Switch (`Usage 0x39`) with logical range 0..7 + null.
- Bluepad32 will map hat positions into `gamepad.dpad`.

## Button Mapping (Usage Page: Button)

Bluepad32's generic parser maps the following button usages:

- Button 1 -> `BUTTON_A`
- Button 2 -> `BUTTON_B`
- Button 4 -> `BUTTON_X`
- Button 5 -> `BUTTON_Y`
- Button 7 -> `BUTTON_SHOULDER_L`
- Button 8 -> `BUTTON_SHOULDER_R`
- Button 0x0b -> `MISC_BUTTON_SELECT`
- Button 0x0c -> `MISC_BUTTON_START`
- Button 0x0d -> `MISC_BUTTON_SYSTEM`
- Button 0x0e -> `BUTTON_THUMB_L`
- Button 0x0f -> `BUTTON_THUMB_R`

Buttons outside this set are ignored by the generic parser.

## Axis Ranges

- Logical min/max will be set to -127..127, report size 8 bits.
- Bluepad32 normalizes to -512..511 internally.

## Competition Firmware Expectations

The competition code uses:

- `axis_y` and `axis_x` for drive (signed).
- `axis_ry` for weapon speed (signed, positive-only after deadzone).
- `BUTTON_SHOULDER_L` + `BUTTON_SHOULDER_R` for estop.
- `BUTTON_B` toggle for arm.
- `BUTTON_A` hold to clear estop.

This mapping aims to keep those controls consistent.
