# Firmware One-Off Tests

This directory contains standalone firmware images for bench testing.
These are not part of the competition firmware and may bypass safety interlocks.

## Build

```bash
export PICO_SDK_PATH=/path/to/pico-sdk
cd firmware/tests
mkdir -p build && cd build
cmake ..
make dshot_beep_test dshot_spin_test
```

## Flash (example)

```bash
picotool reboot -f -u
picotool load -x firmware/tests/build/dshot_spin_test.uf2
```

## Notes

- DShot tests use GP4 (PIN_WEAPON_PWM) and DShot300.
- Bidirectional telemetry is disabled in the spin test for stability.
