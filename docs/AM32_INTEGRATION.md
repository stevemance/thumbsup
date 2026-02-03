# AM32 ESC Integration Guide

## Overview

This document describes the integration between the ThumbsUp robot firmware and AM32-compatible brushless ESCs for weapon motor control.

## What is AM32?

AM32 is open-source firmware for brushless ESC (Electronic Speed Controllers). It provides:
- Advanced motor control algorithms
- Serial configuration protocol
- Optional telemetry (RPM, voltage, current, temperature)
- Firmware updates via serial bootloader
- MSP protocol compatibility for configurators

**Project**: https://github.com/am32-firmware/AM32

## Integration Architecture

```
ThumbsUp Firmware
    ↓
Motor Control Layer (motor_control.c)
    ↓
Protocol Selection
    ├─→ DShot Mode (default)
    │   └─→ Digital protocol with telemetry
    ├─→ PWM Mode (fallback)
    │   └─→ Standard 1000-2000μs servo signals
    └─→ Configuration Mode
        └─→ UART serial for ESC setup
```

## Communication Modes

### 1. PWM Control Mode (Fallback)

**Normal operation** - Standard servo PWM signals:
- Pin: `GP4` (PIN_WEAPON_PWM)
- Frequency: 50Hz
- Pulse width: 1000-2000μs
- No special wiring required

### 2. Configuration Mode (Serial)

**For ESC setup** - UART communication:
- Pin: Same `GP4` (dynamically switched)
- Baud rate: 19200 (config), 115200 (bootloader)
- Protocol: AM32 native + MSP compatibility
- Activated programmatically via `am32_enter_config_mode()`

### 3. DShot Mode (Active)

**Digital control with telemetry**:
- Pin: `GP4` (PIO-based)
- Speed: DShot300 recommended (300kbit/s)
- Benefits:
  - Faster response (up to 8kHz update rate vs 50Hz PWM)
  - Bidirectional telemetry (EDT)
  - More reliable digital protocol
  - No calibration needed

## File Structure

```
firmware/
  include/
    am32_config.h          # AM32 protocol definitions
    dshot.h                # DShot protocol
  src/
    am32_config.c          # Serial configuration implementation
    dshot.c                # DShot implementation
    motor_control.c        # Integrates all protocols

config/am32/
  weapon_esc_config.json   # Recommended ESC settings
  README.md                # Flashing and setup guide

docs/
  AM32_INTEGRATION.md      # This file
```

## Current Implementation Status

### ✅ Implemented
- [x] PWM control (standard servo mode)
- [x] UART mode switching (PWM ↔ Serial)
- [x] AM32 serial protocol framework
- [x] Configuration read/write
- [x] Settings management
- [x] Throttle calibration
- [x] Passthrough mode for external configurators
- [x] Bootloader entry (for firmware updates)
- [x] Factory reset
- [x] PIO-based DShot control (weapon motor)
- [x] EDT bidirectional telemetry decoding
- [x] Telemetry polling in weapon control loop
- [x] Automated integration test (DShot telemetry rate + RPM monotonicity)

### 🚧 Partial / TODO
- [ ] Telemetry integration with status display/safety thresholds
- [ ] MSP protocol wrapper (optional)
- [ ] Automatic ESC detection

## Using AM32 Features

### Read ESC Information

```c
#include "am32_config.h"

am32_info_t info;
if (am32_get_info(&info)) {
    printf("ESC Firmware: %s v%d.%d.%d\n",
           info.firmware_name,
           info.firmware_version[0],
           info.firmware_version[1],
           info.firmware_version[2]);
}
```

### Read Current Settings

```c
am32_config_t config;
if (am32_read_settings(&config)) {
    printf("Motor timing: %d degrees\n", config.motor_timing);
    printf("Current limit: %dA\n", config.current_limit);
    printf("Temperature limit: %d°C\n", config.temperature_limit);
}
```

### Update ESC Settings

```c
am32_config_t config;
am32_apply_weapon_defaults(&config);

// Customize for your motor
config.motor_kv = 1100;
config.motor_poles = 14;
config.motor_timing = 16;
config.current_limit = 40;

if (am32_write_settings(&config)) {
    am32_save_settings();  // Write to EEPROM
}
```

### External Configurator Passthrough

Use the Pico as a USB-to-UART bridge for AM32 Configurator software:

```c
// Enter passthrough mode
am32_passthrough_mode();  // Press ESC key to exit

// Now connect with AM32 Configurator tool via USB serial
```

### Enter Bootloader for Firmware Updates

```c
if (am32_enter_bootloader()) {
    // ESC is now in bootloader mode
    // Use AM32 Configurator to flash new firmware
}
```

## ESC Configuration Best Practices

### Weapon Motor Settings

See `config/am32/weapon_esc_config.json` for complete configuration.

**Critical Settings:**
```json
{
  "motor_direction": "forward",      // Uni-directional only
  "bidirectional_mode": false,
  "brake_on_stop": false,            // IMPORTANT: No brake for weapons!
  "motor_timing": 16,                // Degrees (tune for your motor)
  "startup_power": "medium",
  "temperature_limit": 80,           // Celsius
  "current_limit": 40,               // Amps (match ESC rating)
  "demag_compensation": "high"       // For heavy weapon loads
}
```

### Safety Notes

⚠️ **Always disable brake-on-stop for weapon motors** - Active braking can damage the weapon or robot structure during impacts.

⚠️ **Proper power capacitor** - Use 1000μF low-ESR capacitor near ESC power input to handle weapon spin-up current spikes.

⚠️ **Calibrate throttle range** - Ensure ESC knows 1000μs = stop, 2000μs = full speed.

## DShot Protocol (Active)

### Why DShot?

DShot offers several advantages over PWM:

| Feature | PWM (Current) | DShot (Future) |
|---------|---------------|----------------|
| Update rate | 50Hz | Up to 8kHz |
| Reliability | Analog timing | Digital checksum |
| Calibration | Required | Not needed |
| Telemetry | Separate wire | Bidirectional |
| Response | ~20ms | ~0.125ms |

### DShot Implementation Notes

- **PIO Program**: RP2040 PIO generates precise DShot waveforms
- **DMA Transfer**: TX uses DMA to minimize CPU load
- **EDT Parser**: Bidirectional telemetry decoding is enabled
- **Integration**: Falls back to PWM if DShot init fails

### Telemetry Data (EDT)

When DShot telemetry is enabled:
```c
weapon_telemetry_t telem;
if (weapon_get_telemetry(&telem)) {
    float voltage = telem.voltage_cV / 100.0f;
    float current = telem.current_cA / 100.0f;

    printf("Weapon: %d RPM, %.1fV, %.1fA, %d°C\n",
           telem.rpm, voltage, current, telem.temperature_C);
}
```

## Hardware Connections

### Current Setup (DShot + telemetry)

Signal wiring (single wire, bidirectional):
```
RP2040 Pico W          AM32 ESC
┌──────────┐          ┌────────┐
│   GP4────┼─────────→│ Signal │
│  3.3V─[2.2k]───────→│ Signal │
│   GND────┼─────────→│  GND   │
└──────────┘          └────────┘
```

Power + motor wiring:
```
RP2040 Pico W          AM32 ESC            Brushless Motor
┌──────────┐          ┌────────┐          ┌──────┐
│          │          │        │          │      │
│  VSYS────┼──(BEC)──→│  5V    │          │  A   │
│          │          │        ├─────────→│  B   │
│   GND────┼─────────→│  GND   │          │  C   │
└──────────┘          │        │          └──────┘
                      │  BAT+──┼───── 3S LiPo +
                      │  BAT───┼───── 3S LiPo -
                      └────────┘
```

### PWM Fallback

PWM uses the same GP4 signal line without telemetry pull-up.

## Automated Integration Test

Use the integration build to validate DShot telemetry reliability without a controller.

```bash
python3 tools/run_integration_test.py --voltage 12.6 --current 3.0 --channel 1
```

What it does:
- Builds + flashes `thumbsup_integration.uf2`
- Powers the PSU via `labctl` and logs voltage/current
- Auto-runs the DShot integration sequence over USB serial
- Reports telemetry request/response rate and RPM monotonicity

Notes:
- The integration test attempts to enter AM32 config mode and enable telemetry/bidirectional flags if needed.
- Telemetry voltage/current/temperature are ESC-calibrated values; some ESCs require calibration or may report scaled values.

## Debugging

### Check ESC Communication

```c
// Test UART switching
if (am32_enter_config_mode()) {
    printf("ESC responded to config mode\n");

    am32_info_t info;
    if (am32_get_info(&info)) {
        printf("ESC detected: %s\n", info.firmware_name);
    }

    am32_exit_config_mode();
}
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No ESC response | Wrong baud rate | Check 19200 for config mode |
| Timeout errors | Bad connection | Check wiring and ground |
| Motor won't spin | Not calibrated | Run `am32_calibrate_throttle()` |
| Stuttering | Wrong timing | Adjust `motor_timing` setting |
| Overheating | Current too high | Reduce `current_limit` |

## Reference Documentation

- **AM32 Project**: https://github.com/am32-firmware/AM32
- **AM32 DeepWiki**: https://deepwiki.com/am32-firmware/AM32
- **DShot Specification**: https://github.com/betaflight/betaflight/wiki/DSHOT-ESC-Protocol
- **AM32 Discord**: https://discord.gg/h4QNyGd

## Contributing

If you implement additional features (e.g., telemetry-driven safety thresholds):

1. Update this documentation
2. Add examples to `config/am32/`
3. Update function comments in header files
4. Test thoroughly with actual ESC hardware

## Version History

- **v1.0** (2024-11-18): Initial AM32 integration with PWM control
- **v1.1** (2026-02-02): DShot control with bidirectional telemetry decode/polling
