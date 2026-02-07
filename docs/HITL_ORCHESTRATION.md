# HITL Orchestration (Robot + Gamepad + Host)

This repo supports a fully automated hardware-in-the-loop (HITL) setup with:

1. **Robot Pico W** running the **production competition Bluetooth stack** (Bluepad32) plus a USB HITL console.
2. **Gamepad Pico W** running a **Bluetooth HID gamepad emulator** controlled over USB serial.
3. A host-side **orchestrator** that builds, flashes, runs tests, and produces pass/fail artifacts.

The goal is to exercise the *real* competition firmware path end-to-end without requiring a physical controller.

## Components

### 1) Robot Firmware (`thumbsup_hitl`)

Robot stays on the Bluetooth competition implementation (Bluepad32), but enables a USB CDC console for:

- Status streaming (machine parsable)
- Deterministic overrides (battery voltage)
- Bluetooth key management (pairing reset / inspection)

Relevant files:

- `firmware/src/hitl_console.c`
- `firmware/include/hitl_console.h`
- `firmware/src/hitl_overrides.c`
- `firmware/include/hitl_overrides.h`
- `firmware/src/bluetooth_platform.c`
- `firmware/src/main.c`
- `firmware/CMakeLists.txt`

HITL console commands (robot):

- `HITL STATUS`
- `HITL BTADDR`
- `HITL BTKEYS CLEAR`
- `HITL BTKEYS LIST`
- `HITL BATTERY <mv>`
- `HITL BATTERY OFF`
- `HITL TELEM`
- `HITL TELEMSTATS`

### 2) Gamepad Emulator Firmware (`thumbsup_controller_emulator`)

This Pico W advertises as a Bluetooth Classic HID gamepad and accepts simple text commands over USB serial to set:

- Buttons
- Axes
- Dpad / hat

Relevant files:

- `controller_emulator/src/main.c`
- `docs/controller_emulator_mapping.md`

Serial commands (gamepad):

- `RESET`
- `KEYS CLEAR`
- `CONNECT <bt_addr>`
- `DISCONNECT`
- `BTN <name> <0|1>`
- `AXIS <LX|LY|RX|RY> <-127..127>`
- `STICK <L|R> <x> <y>`
- `DPAD <CENTER|UP|...>`

### 3) Host Orchestrator (`tools/hitl_orchestrator.py`)

The orchestrator:

1. Builds robot + gamepad UF2s
2. Flashes both Picos without BOOTSEL using `picotool` (reset-to-BOOTSEL)
3. Reboots both into application mode at the start of the test for clean state
4. Runs an automated smoke suite with pass/fail
5. Emits logs + a JSON report under `hitl_logs/`

Relevant files:

- `tools/hitl_orchestrator.py`

Run:

```bash
python3 tools/hitl_orchestrator.py --suite smoke
```

Drive PWM end-to-end (no motor power required):

```bash
python3 tools/hitl_orchestrator.py --suite drive_e2e
```

Disconnect failsafe (drive outputs return to neutral after controller disconnect):

```bash
python3 tools/hitl_orchestrator.py --suite disconnect_failsafe
```

Active weapon spin suite (requires PSU channel powering the ESC/motor):

```bash
python3 tools/hitl_orchestrator.py --suite weapon_spin --spin-axis 60 --spin-hold-s 5
```

Active drive spin suite (requires PSU channel powering the drive ESC/motors):

```bash
python3 tools/hitl_orchestrator.py --suite drive_spin --psu-drive-channel 1 --drive-spin-hold-s 2.5
```

Emergency stop while actively driving (requires PSU channel powering the drive ESC/motors):

```bash
python3 tools/hitl_orchestrator.py --suite estop_drive --psu-drive-channel 1
```

Weapon disarmed guard (requires PSU channel powering the weapon ESC/motor):

```bash
python3 tools/hitl_orchestrator.py --suite weapon_disarmed_guard --psu-channel 1
```

Emergency stop while weapon is spinning (requires PSU channel powering the weapon ESC/motor):

```bash
python3 tools/hitl_orchestrator.py --suite estop_weapon --psu-channel 1
```

Active safety invariants (estop drive + disconnect failsafe + weapon guard + estop weapon):

```bash
python3 tools/hitl_orchestrator.py --suite safety_active --psu-channel 1 --psu-drive-channel 1
```

Full end-to-end suite (smoke + drive + safety + weapon):

```bash
python3 tools/hitl_orchestrator.py --suite full_e2e
```

Artifacts:

- `hitl_logs/run_*/steps/*/robot_serial.log`
- `hitl_logs/run_*/steps/*/gamepad_serial.log`
- `hitl_logs/run_*/steps/*/weapon_spin_result.json` (PSU + telemetry summary)
- `hitl_logs/run_*/steps/*/drive_spin_result.json`
- `hitl_logs/run_*/steps/*/drive_e2e_result.json`
- `hitl_logs/run_*/steps/*/disconnect_failsafe_result.json`
- `hitl_logs/latest_orchestrator_report.json`

## Reports (MD/PDF + Plots)

Each orchestrator invocation also creates a single run directory:

- `hitl_logs/run_<timestamp>_<suite>/`

Inside that directory you'll find:

- `orchestrator_report.json` (machine-readable report with step results and artifact paths)
- `report.md` (human readable report, includes plots)
- `report.pdf` (multi-page PDF with the same core plots + a summary page)
- `steps/` (per-step logs + JSON results)
- `plots/` (generated PNG plots)

Convenience pointer:

- `hitl_logs/latest_run_dir.txt`

To skip report generation:

```bash
python3 tools/hitl_orchestrator.py --no-report ...
```

## Pass/Fail Behavior (Smoke Suite)

The smoke suite is intentionally safe: it does **not** command motor speed.

It verifies:

1. Robot HITL console is alive (`HITL STATUS` samples observed)
2. Battery override is applied (`HITL BATTERY 12500`)
3. Bluetooth pairing/connect succeeds (controller becomes `ready=1`)
4. Weapon arm toggle works (B press sets `armed=1`)
5. Emergency stop works (L1+R1 sets `failsafe=1`)
6. Emergency stop clear works (hold A for ~2s returns `failsafe=0`)
7. Re-arm + disarm works (debounce-aware timing)

## Keeping Devices Straight

Use stable udev symlinks for the two dedicated HITL Picos:

- `/dev/ttyHITL_ROBOT`
- `/dev/ttyHITL_GAMEPAD`

Setup details are in `docs/hitl_device_setup.md`.

## How To Extend (Full Bot HITL)

The intended direction is to add suites that validate robot subsystems using the same production code path:

1. **Drive HITL**
   - Add orchestrator sequences that command sticks (LX/LY) and validate:
     - Motor PWM outputs (via existing status or additional HITL status fields)
     - Safety behavior (failsafe cutoff, deadzones)
     - Optional: PSU current signature via `labctl psu snapshot` or scope capture
2. **Weapon + Telemetry HITL**
   - Add a suite that:
     - Arms weapon
     - Commands a small safe throttle for a fixed duration (with PSU enabled)
     - Validates DShot telemetry decode stats (`HITL TELEMSTATS`) and telemetry freshness
3. **Sensor/Analog Overrides**
   - Expand `hitl_overrides` to support:
     - ADC overrides (battery, any analog sensors)
     - Digital input overrides (safety switch) if needed for automation

Design principles:

- Prefer adding **introspection** and **override hooks** behind `HITL_CONSOLE` to keep production behavior unchanged.
- Keep suites **safe by default** (PSU off, no spin) and require explicit flags for “active” tests.
- Treat lab equipment interactions as best-effort (don’t fail a suite because a scope/PSU is offline).
