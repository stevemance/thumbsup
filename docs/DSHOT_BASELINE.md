# DShot Baseline (Known-Good Spin Test)

This file records the last known-good DShot baseline that spins the weapon motor.

## Baseline Summary
- Date: 2026-01-29T17:24:59Z
- Test firmware: `firmware/tests/build/dshot_spin_test.uf2`
- SHA256: `b3112b6297903f346bd9d14098ab961b18bbcdd47f08b3f9ebd958b139638930`
- Source: `firmware/src/dshot_spin_test.c`

## DShot Settings
- GPIO: `PIN_WEAPON_PWM` (GP4)
- Speed: DShot300
- Bidirectional: off
- Pole pairs: 7
- Update rate: 500 Hz (2 ms step)

## Test Sequence
1) Arm: throttle 0 for 5s
2) `DSHOT_CMD_3D_MODE_OFF` x3
3) `DSHOT_CMD_SPIN_DIRECTION_NORMAL` x3
4) Throttle ramp: 200 → 500 → 1000 → 1500 → 1800 (2s each)
5) Stop: throttle 0 for 4s
6) Repeat

## Build + Flash (repeatable)
```bash
cd firmware/tests/build
make dshot_spin_test
picotool reboot -f -u
picotool load -x firmware/tests/build/dshot_spin_test.uf2
```

## Notes
- Setting bidirectional to true (telemetry enabled) stops motor spin on this ESC.
