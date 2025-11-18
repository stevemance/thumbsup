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

**Project**: https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware

## Integration Architecture

```
ThumbsUp Firmware
    ↓
Motor Control Layer (motor_control.c)
    ↓
Protocol Selection
    ├─→ PWM Mode (default)
    │   └─→ Standard 1000-2000μs servo signals
    ├─→ DShot Mode (future)
    │   └─→ Digital protocol with telemetry
    └─→ Configuration Mode
        └─→ UART serial for ESC setup
```

## Communication Modes

### 1. PWM Control Mode (Active)

**Normal operation** - Standard servo PWM signals:
- Pin: `GP2` (PIN_WEAPON_PWM)
- Frequency: 50Hz
- Pulse width: 1000-2000μs
- No special wiring required

### 2. Configuration Mode (Serial)

**For ESC setup** - UART communication:
- Pin: Same `GP2` (dynamically switched)
- Baud rate: 19200 (config), 115200 (bootloader)
- Protocol: AM32 native + MSP compatibility
- Activated programmatically via `am32_enter_config_mode()`

### 3. DShot Mode (Future)

**Digital control with telemetry**:
- Pin: `GP2` (PIO-based)
- Speed: DShot300 recommended (300kbit/s)
- Benefits:
  - Faster response (8kHz update rate vs 50Hz PWM)
  - Bidirectional telemetry (EDT)
  - More reliable digital protocol
  - No calibration needed

## File Structure

```
firmware/
  include/
    am32_config.h          # AM32 protocol definitions
    dshot.h                # DShot protocol (future)
  src/
    am32_config.c          # Serial configuration implementation
    dshot.c                # DShot implementation (future)
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

### 🚧 Partial / TODO
- [ ] Complete PIO-based DShot implementation
- [ ] EDT bidirectional telemetry parsing
- [ ] MSP protocol wrapper (optional)
- [ ] Automatic ESC detection
- [ ] Telemetry integration with status display

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

## DShot Protocol (Future)

### Why DShot?

DShot offers several advantages over PWM:

| Feature | PWM (Current) | DShot (Future) |
|---------|---------------|----------------|
| Update rate | 50Hz | Up to 8kHz |
| Reliability | Analog timing | Digital checksum |
| Calibration | Required | Not needed |
| Telemetry | Separate wire | Bidirectional |
| Response | ~20ms | ~0.125ms |

### DShot Implementation Plan

1. **PIO Program**: Use RP2040's PIO to generate precise DShot waveforms
2. **DMA Transfer**: Efficient bit streaming without CPU load
3. **EDT Parser**: Decode bidirectional telemetry frames
4. **Integration**: Fallback to PWM if DShot not supported

### Telemetry Data (EDT)

When DShot telemetry is enabled:
```c
dshot_telemetry_t telem;
if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
    uint16_t rpm = dshot_erpm_to_rpm(telem.erpm, 7);  // 14 poles = 7 pairs
    float voltage = telem.voltage_cV / 100.0f;
    float current = telem.current_cA / 100.0f;

    printf("Weapon: %d RPM, %.1fV, %.1fA, %d°C\n",
           rpm, voltage, current, telem.temperature_C);
}
```

## Hardware Connections

### Current Setup (PWM)

```
RP2040 Pico W          AM32 ESC            Brushless Motor
┌──────────┐          ┌────────┐          ┌──────┐
│          │          │        │          │      │
│   GP2────┼─────────→│ Signal │          │  A   │
│          │          │        ├─────────→│  B   │
│   GND────┼─────────→│  GND   │          │  C   │
│          │          │        │          └──────┘
│  VSYS────┼──(BEC)──→│  5V    │
└──────────┘          │        │
                      │  BAT+──┼───── 3S LiPo +
                      │  BAT───┼───── 3S LiPo -
                      └────────┘
```

### Future DShot + Telemetry

```
RP2040 Pico W          AM32 ESC
┌──────────┐          ┌────────┐
│          │          │        │
│   GP2────┼────┬────→│ Signal │  (DShot out)
│          │    │     │        │
│          │    └────→│  T-RX  │  (Telemetry in, future)
│          │          │        │
│   GND────┼─────────→│  GND   │
└──────────┘          └────────┘
```

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

- **AM32 Project**: https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware
- **AM32 Wiki**: https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware/wiki
- **Serial Protocol**: https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware/wiki/Serial-Protocol
- **DShot Specification**: https://github.com/betaflight/betaflight/wiki/DSHOT-ESC-Protocol
- **AM32 Discord**: https://discord.gg/h4QNyGd

## Contributing

If you implement additional features (e.g., complete DShot telemetry):

1. Update this documentation
2. Add examples to `config/am32/`
3. Update function comments in header files
4. Test thoroughly with actual ESC hardware

## Version History

- **v1.0** (2024-11-18): Initial AM32 integration with PWM control
- **v1.1** (future): DShot implementation with bidirectional telemetry
