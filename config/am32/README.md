# AM32 ESC Configuration

This directory contains configuration files for the AM32 weapon ESC.

## Files Used By HITL

- `weapon_esc_expected.hexcfg`: canonical 192-byte expected EEPROM image (hex text).
- `weapon_esc_config.json`: human-readable notes/settings reference.
- `tools/am32_config_codec.py`: bidirectional converter (`yaml <-> hexcfg/bin`).

`tools/hitl_orchestrator.py` uses `weapon_esc_expected.hexcfg` during the `AM32 Provision` step:

1. Flashes `am32_flasher_service` onto the HITL robot Pico.
2. Reads current ESC config.
3. Compares against expected config in git.
4. Writes only when different.
5. Verifies via readback.
6. Flashes competition firmware back to the robot Pico.

You can also point orchestrator directly at YAML:

```bash
python3 tools/hitl_orchestrator.py --suite smoke --am32-config config/am32/weapon_esc_expected.yaml
```

## YAML / Binary Conversion

Compile YAML to hex-text image:

```bash
python3 tools/am32_config_codec.py compile \
  --input config/am32/weapon_esc_expected.yaml \
  --output config/am32/weapon_esc_expected.hexcfg
```

Compile YAML to binary image:

```bash
python3 tools/am32_config_codec.py compile \
  --input config/am32/weapon_esc_expected.yaml \
  --output /tmp/weapon_esc.bin --format bin
```

Decompile existing image to YAML:

```bash
python3 tools/am32_config_codec.py decompile \
  --input config/am32/weapon_esc_expected.hexcfg \
  --output config/am32/weapon_esc_expected.yaml
```

## Refreshing Expected Config In Git

Use this flow when you have a known-good ESC setup and want to make it the new baseline:

```bash
# 1) Read current ESC config (service firmware must be running on HITL robot Pico)
python3 tools/am32_pico_flasher.py --port /dev/ttyHITL_ROBOT read-config --out /tmp/am32_current.bin

# 2) Convert to tracked hex-text artifact
xxd -p -c48 /tmp/am32_current.bin > config/am32/weapon_esc_expected.hexcfg
```

Then review and commit `config/am32/weapon_esc_expected.hexcfg`.

## Weapon ESC Setup

The weapon uses an AM32 40A 32-bit ESC with the following key settings:

### Critical Settings

- **Motor Direction**: Forward only (unidirectional)
- **Brake on Stop**: DISABLED (important for weapon safety)
- **PWM Range**: 1000-2000μs standard servo signal
- **Motor Timing**: 16 degrees (optimal for F2822-1100KV)

### Flashing AM32 Firmware

1. **Download Tools**:
   - AM32 Configuration Tool: [GitHub Release](https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware/releases)
   - STLink software (if using STLink programmer)
   - USB-TTL adapter (alternative method)

2. **Connection Methods**:

   **Method A - SWD Programming (Recommended)**:
   ```
   STLink V2 -> ESC
   SWDIO -> SWDIO pad
   SWCLK -> SWCLK pad
   GND -> GND
   3.3V -> 3.3V (optional, ESC can be powered separately)
   ```

   **Method B - Betaflight Passthrough**:
   - Connect ESC to flight controller
   - Use AM32 configurator in passthrough mode

3. **Flashing Process**:
   - Connect programmer to ESC
   - Open AM32 Configuration Tool
   - Select correct target (check ESC MCU type)
   - Load firmware file
   - Click "Flash"
   - Wait for completion

### Configuration Steps

1. **Connect to Configurator**:
   - Power ESC with 3S battery
   - Connect via programmer or serial
   - Open AM32 Configurator

2. **Load Settings**:
   - Import `weapon_esc_config.json`
   - Or manually set each parameter

3. **Key Parameters to Verify** (the authoritative values are in
   `weapon_esc_expected.yaml`, which the HITL tools apply automatically):
   ```
   Input: DShot (bidirectional telemetry on)
   Motor Direction: Forward
   Bidirectional (3D mode): ON   - reverse spin on ZL
   Brake on Stop: OFF            - the drum coasts
   Complementary PWM: OFF        - sine start is then unused (set OFF)
   Timing: auto advance ON
   Temperature Limit: 70°C       - MCU internal sensor
   Current Limit: OFF            - this ESC has no working current sensor
   Stuck Rotor / Stall Protection: OFF
   ```

4. **Save and Write**:
   - Click "Write Settings"
   - Power cycle ESC

### Throttle Calibration

**Important**: Perform this with motor disconnected!

1. Connect ESC to Pico (signal and ground only)
2. Power on Pico in calibration mode:
   - Hold button while powering on
   - Or use serial command
3. ESC will enter calibration:
   - Two beeps = high point set
   - One beep = low point set
   - Musical tones = calibration complete

### Testing Procedure

1. **Bench Test** (No Propeller):
   - Connect motor without weapon attached
   - Test throttle response
   - Verify smooth acceleration
   - Check for unusual sounds/vibrations

2. **Load Test** (With Weapon):
   - Secure robot in test box
   - Start at low throttle
   - Gradually increase to full
   - Monitor temperature

3. **Safety Checks**:
   - Verify instant stop on signal loss
   - Test emergency stop function
   - Confirm arming sequence works

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Motor doesn't spin | Check throttle calibration, verify 1000μs = stop |
| Motor stutters on startup | Increase startup power, adjust timing |
| ESC gets hot | Check current limit, improve cooling |
| Random stops | Check capacitor, reduce current limit |
| Won't arm | Ensure throttle at minimum during power-on |

### LED Indicators

AM32 ESCs typically use LED patterns:

- **Solid**: Armed and ready
- **Slow blink**: Waiting for signal
- **Fast blink**: Error or protection active
- **Double blink**: Throttle calibration mode

### Performance Tuning

For optimal weapon performance:

1. **Startup Power**: Medium-High for quick spin-up
2. **Motor Timing**: 16-20° for outrunner motors
3. **Demag Compensation**: High for heavy loads
4. **PWM Frequency**: 24-48kHz for smooth operation

### Safety Notes

⚠️ **WARNING**: Weapon motors are dangerous!

- Always remove weapon before testing
- Use proper test box/arena
- Have emergency stop ready
- Never bypass safety features
- Keep hands clear of weapon path

### Support

For AM32 specific issues:
- [AM32 Documentation](https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware/wiki)
- [AM32 Discord](https://discord.gg/h4QNyGd)

For robot-specific issues:
- Check main README.md
- Review wiring diagrams
- Verify config.h settings match
