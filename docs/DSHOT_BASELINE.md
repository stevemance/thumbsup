# DShot Baseline (Known-Good Spin Test)

This file records the last known-good DShot baseline that spins the weapon motor.

## Baseline Summary
- Date: 2026-02-02
- Test firmware: `firmware/tests/build/dshot_telemetry_spin_test.uf2`
- Source: `firmware/tests/src/dshot_telemetry_spin_test.c`

## DShot Settings
- GPIO: `PIN_WEAPON_PWM` (GP4)
- Speed: DShot300
- Bidirectional: on (EDT telemetry)
- Pole pairs: 7
- Update rate: 500 Hz (2 ms step)
- Telemetry request: every frame

## Test Sequence
1) Arm: throttle 0 for 5s
2) `DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE` x6
3) `DSHOT_CMD_3D_MODE_OFF` x6
4) `DSHOT_CMD_SPIN_DIRECTION_NORMAL` x6
5) Throttle ramp: 200 → 500 → 1000 → 1500 → 1800 (2s each)
6) Stop: throttle 0 for 4s
7) Repeat

## Build + Flash (repeatable)
```bash
cd firmware/tests/build
make dshot_telemetry_spin_test
picotool reboot -f -u
picotool load -x firmware/tests/build/dshot_telemetry_spin_test.uf2
```

## Notes
- Telemetry sampling uses 42 samples (21 bits @ 2x) at ~1.25us cadence.
