# HITL Device Setup

This repo supports a two-Pico HITL setup:

- `ThumbsUp HITL Robot` (runs competition firmware)
- `ThumbsUp HITL Gamepad` (runs the controller emulator)

## Build + Flash

Robot firmware (competition build):

```bash
export BLUEPAD32_ROOT=/home/smance/bluepad32
export PICO_SDK_PATH=/home/smance/pico/pico-sdk
cmake -S firmware -B firmware/build
cmake --build firmware/build --target thumbsup
picotool load -f -x firmware/build/thumbsup.uf2
```

Controller emulator:

```bash
export PICO_SDK_PATH=/home/smance/pico/pico-sdk
cmake -S controller_emulator -B controller_emulator/build
cmake --build controller_emulator/build
picotool load -f -x controller_emulator/build/thumbsup_controller_emulator.uf2
```

Note: If `picotool load -f` cannot reboot a device into BOOTSEL, press the
BOOTSEL button while plugging the Pico in, then re-run the `picotool load`.

## Stable Aliases (udev)

Create `/etc/udev/rules.d/99-thumbsup-pico.rules` with your device serials:

```text
# ThumbsUp HITL Pico W devices
SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", MODE:="0660", GROUP:="plugdev", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", MODE:="0660", GROUP:="plugdev", TAG+="uaccess"

# Stable aliases for HITL units (match on unique serial)
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{serial}=="<ROBOT_SERIAL>", SYMLINK+="ttyHITL_ROBOT"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{serial}=="<GAMEPAD_SERIAL>", SYMLINK+="ttyHITL_GAMEPAD"
```

Reload rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
```

Find serials:

```bash
udevadm info -a -n /dev/ttyACM0 | rg -n "serial"
```

## Usage

- Robot serial: `/dev/ttyHITL_ROBOT`
- Gamepad serial: `/dev/ttyHITL_GAMEPAD`

Example:

```bash
./tools/serial_hitl.py --auto
./tools/emulator_control.py --auto --command "STATE"
```

BOOTSEL mode uses `RP2 Boot` and does not preserve these symlinks.
