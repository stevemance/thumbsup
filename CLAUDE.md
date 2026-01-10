# ThumbsUp Robot - Claude Development Notes

This file contains useful information for Claude Code when working on the ThumbsUp combat robot firmware.

## Project Structure

```
thumbsup/
├── firmware/               # Main firmware source
│   ├── src/               # Source files
│   │   ├── main.c         # Main application entry
│   │   ├── dshot.c        # DShot ESC protocol implementation
│   │   ├── dshot.pio      # PIO assembly for DShot timing
│   │   ├── motor_control.c # Motor control abstraction
│   │   └── ...
│   ├── include/           # Header files
│   ├── build/             # Build artifacts (auto-generated)
│   └── CMakeLists.txt     # Build configuration
└── HARDWARE_BRINGUP_PLAN.md # Systematic testing protocol
```

## Hardware

- **MCU**: Raspberry Pi Pico W (RP2040)
- **Motor**: FingerTech Silver Spark F2822-1100KV (9.9A max, 14 poles)
- **ESC**: AT32F421-based AM32 ESC firmware
- **Protocol**: DShot300 (digital ESC communication)
- **Controller**: Bluetooth via Bluepad32

## Build System

### Prerequisites

```bash
export BLUEPAD32_ROOT=/home/smance/playbox/bluepad32
export PICO_SDK_PATH=/home/smance/pico/pico-sdk
```

### Building

From `/home/smance/projects/thumbsup/firmware/build`:

```bash
# Configure (first time only)
BLUEPAD32_ROOT=/home/smance/playbox/bluepad32 PICO_SDK_PATH=/home/smance/pico/pico-sdk cmake ..

# Build main firmware
BLUEPAD32_ROOT=/home/smance/playbox/bluepad32 PICO_SDK_PATH=/home/smance/pico/pico-sdk make thumbsup

# Build specific test firmware
BLUEPAD32_ROOT=/home/smance/playbox/bluepad32 PICO_SDK_PATH=/home/smance/pico/pico-sdk make phase3_motor_spin
```

### Flashing Firmware

**Preferred Method (picotool):**
```bash
# Flash and run without manual BOOTSEL button press
picotool load -x firmware.uf2

# Examples:
picotool load -x thumbsup.uf2
picotool load -x phase3_motor_spin.uf2
```

**Manual Method (BOOTSEL mode):**
```bash
# 1. Hold BOOTSEL button while connecting USB (or press BOOTSEL + reset)
# 2. Mount the Pico
udisksctl mount -b /dev/sdb1

# 3. Copy firmware
cp firmware.uf2 /media/smance/RPI-RP2/

# 4. Sync and the Pico will auto-reboot
sync
```

## Test Firmwares

### phase2_dshot_verify
- Purpose: Generate DShot test patterns for oscilloscope verification
- Outputs: Throttle values 0, 48, 200, 500, 1000 with 3s hold each
- Use: Verify DShot signal timing and encoding

### phase3_motor_spin
- Purpose: Test ESC arming and motor spinning
- Sequence: 0 → 500 → 1000 → 1500 → 0 throttle
- Update rate: 500Hz (2ms between packets)
- Features: Bidirectional DShot, progressive throttle ramp

### esc_test
- Purpose: Standalone AM32/DShot testing
- Tests: UART config mode + DShot signals

## DShot Protocol

### Key Parameters
- **Speed**: DShot300 (3.33μs bit period)
- **Update Rate**: 500Hz (2ms between packets) - ESCs expect continuous updates
- **Throttle Range**: 0-47 reserved, 48-2047 valid throttle
- **Packet Structure**: [15:5]=throttle, [4]=telemetry, [3:0]=CRC4

### Critical Implementation Details
- **Bit Encoding**: MSB-first transmission (shift right)
- **PIO Timing**: 15 cycles per bit
- **Bidirectional Mode**: Supports EDT telemetry (voltage, current, temp, RPM)

### Common Issues Fixed
1. **MSB/LSB Bug**: OSR must be configured for shift RIGHT (MSB first)
2. **Update Rate**: 100ms between packets is too slow - ESCs need 1-2ms
3. **Clock Divider**: Must use 15 cycles per bit, not 13

## AM32 ESC Configuration

### Required Settings (via web configurator at https://am32.ca/)
- **Protocol**: DShot (auto-detects speed)
- **Motor Poles**: 14 (for F2822 motor)
- **Current Limit**: 10A (CRITICAL - motor max is 9.9A)
- **Temperature Limit**: 70°C
- **3D Mode**: Disabled (for combat robot)
- **Complementary PWM**: Enabled or disabled (test both if issues)
- **Startup Power**: 60-100% (higher if motor won't start)
- **Stuck Rotor Protection**: Can disable for troubleshooting

### Arming Behavior
- Send throttle=0 continuously for ~2 seconds
- ESC will beep when armed (different tone)
- During active throttle: ESC silent (no beeps = working correctly)
- Between tests (no signal): ESC beeps (signal loss detection)

## Debugging Tips

### Oscilloscope Verification
- **Timebase**: 20μs/div for DShot300
- **Expected Period**: 3.33μs (rise to rise)
- **Logic 0**: HIGH ~890-1000ns (4 PIO cycles)
- **Logic 1**: HIGH ~1.7-1.9μs (8 PIO cycles)
- **Must see TWO distinct pulse widths** (all same width = LSB/MSB bug)

### Serial Console
- USB serial enabled on main and test firmwares
- DShot commands logged with throttle values and hex encoding
- Watch for "DSHOT SEND" messages to verify packets being sent

### Common ESC States
- **Continuous beeping every ~3s**: No signal or signal too slow
- **Different beep on power-up**: ESC armed successfully
- **Silent during throttle commands**: Working correctly
- **Beeping during throttle**: Error - check update rate or config

## Git Status

Current branch: main
Recent commits focused on:
- DShot timing fixes (MSB/LSB, update rate, clock divider)
- Race condition fixes
- Motor linearization system
- Emergency stop safety improvements

## Resources

- [AM32 Firmware Documentation](https://wiki.am32.ca/)
- [DShot Protocol Guide](https://brushlesswhoop.com/dshot-and-bidirectional-dshot/)
- [Hardware Bringup Plan](HARDWARE_BRINGUP_PLAN.md)
