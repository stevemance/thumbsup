# ThumbsUp Controller Emulator (Pico W)

This firmware turns a Pico W into a generic Bluetooth HID gamepad that Bluepad32 can
pair with. It is intended for HITL automation, driven over USB CDC commands.

The HID report mapping is documented in `docs/controller_emulator_mapping.md`.

## Build

```bash
export PICO_SDK_PATH=/home/smance/pico/pico-sdk
mkdir -p controller_emulator/build
cd controller_emulator/build
cmake ..
make -j4
```

The output UF2 is `thumbsup_controller_emulator.uf2`.

## Flash

```bash
picotool load -f -x thumbsup_controller_emulator.uf2
```

## Pairing

1. Power on the robot (Bluepad32 host).
2. Put the robot into pairing mode (as you would for a normal controller).
3. Power the Pico W emulator; it advertises as `ThumbsUp HITL Gamepad`.

## USB Commands (115200 baud)

- `BTN <name> <0|1>`
- `AXIS <LX|LY|RX|RY> <value -127..127>`
- `STICK <L|R> <x> <y>`
- `DPAD <CENTER|UP|UP_RIGHT|RIGHT|DOWN_RIGHT|DOWN|DOWN_LEFT|LEFT|UP_LEFT>`
- `RESET`
- `STATE`
- `HELP`

Button names: `A`, `B`, `X`, `Y`, `L1`, `R1`, `L2`, `R2`, `SELECT`, `START`, `HOME`, `L3`, `R3`.

You can send commands with `tools/emulator_control.py`, for example:

```bash
./tools/emulator_control.py --port /dev/ttyACM0 --command "BTN B 1"
```

## Notes

- This uses a generic HID descriptor so Bluepad32 parses it via the generic driver.
- The right-stick Y axis is sent as `RZ` usage to keep it signed (Bluepad32 treats `RY` as a pedal).
