# ThumbsUp - Antweight Combat Robot Control System

A complete control system for a 1lb (454g) combat robot using Raspberry Pi Pico W and Bluetooth gamepad control.

## Features

- **Bluetooth Control**: Universal gamepad support via Bluepad32 library (Xbox, PlayStation, Switch Pro, etc.)
- **Differential Drive**: Tank-style mixing with exponential curves for smooth control
- **Weapon Control**: Variable speed brushless weapon with safety arming sequence
- **Safety Systems**: Multiple failsafes including connection loss detection and battery monitoring
- **Status Indicators**: LED feedback for system state, weapon armed, and battery status

## Hardware Components

### Core Electronics
- **Microcontroller**: Raspberry Pi Pico W
- **Power**: 3S LiPo battery (11.1V nominal)

### Motor System
- **Drive Motors**: Repeat Mini Brushed Mk2 (3mm shaft)
- **Drive ESC**: 2-channel brushed motor controller
- **Weapon Motor**: F2822-1100KV brushless outrunner
- **Weapon ESC**: AM32 40A 32-bit ESC

### Control
- **Controller**: Any Bluetooth gamepad supported by Bluepad32
- **Protocol**: Bluetooth Classic (BR/EDR) and BLE support
- **Supported Controllers**: Xbox One/Series, PlayStation 3/4/5, Switch Pro, 8BitDo, and more

## Pin Configuration

| Pin | Function | Description |
|-----|----------|-------------|
| GP2 | PWM Output | Left drive motor |
| GP3 | PWM Output | Right drive motor |
| GP4 | PWM Output | Weapon motor |
| GP5 | GPIO Output | Status LED |
| GP6 | GPIO Output | Armed LED |
| GP7 | GPIO Output | Battery LED |
| GP8 | GPIO Input | Safety button (optional) |
| GP26 | ADC Input | Battery voltage monitor |
| VSYS | Power In | 5V from ESC BEC |
| GND | Ground | Common ground |

## Documentation

### 📖 User Manuals
- **[User Manual](docs/USER_MANUAL.md)** - Complete operating instructions, safety procedures, and troubleshooting
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Single-page quick reference for competition use
- **[Hardware Setup](docs/HARDWARE_SETUP.md)** - Complete pin configuration and wiring guide
- **[Building Guide](docs/building.md)** - Compilation and setup instructions
- **[Wiring Guide](docs/wiring_guide.md)** - Hardware connection diagrams

### Control Mapping Summary

| Control | Function |
|---------|----------|
| Left Stick | Drive control (forward/back + turning) |
| Right Stick Y | Weapon speed control (when armed) |
| B Button | Arm/disarm weapon toggle |
| A Button (hold 2s) | Clear emergency stop |
| L1 + R1 | Emergency stop (all motors) |

## Safety Features

### Startup Safety Tests
The robot performs 6 critical safety tests on every startup:

1. **Motor Initialization** - Verifies all motors start in safe positions
2. **Weapon Safety** - Confirms weapon starts disarmed and interlocks work
3. **Failsafe System** - Tests signal loss detection (1.5 second timeout)
4. **Battery Monitoring** - Validates voltage sensing and thresholds
5. **Emergency Stop** - Verifies E-stop functionality
6. **Overflow Protection** - Ensures calculation safety

If any test fails, the robot enters lockout mode with rapid LED flashing and will not operate.

### Runtime Safety Features
- **Connection failsafe** - Motors stop after 1.5s signal loss
- **Low battery protection** - Weapon disabled below 11.1V
- **Emergency stop** - L1+R1 instantly stops all motors
- **Continuous monitoring** - Safety checks run every 10ms
- **Violation counting** - Multiple violations trigger automatic shutdown

## Firmware Modes

The ThumbsUp firmware supports two different build modes:

1. **Competition Mode** (Default) - Bluetooth gamepad control for combat
2. **Diagnostic Mode** - WiFi web dashboard for testing and configuration

**IMPORTANT**: Due to hardware limitations of the CYW43439 chip, WiFi and Bluetooth cannot run simultaneously. You must choose which mode to build at compile time.

## Building the Firmware

### Prerequisites

1. Install the Raspberry Pi Pico SDK:
```bash
git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init
export PICO_SDK_PATH=$PWD
```

2. Install Bluepad32:
```bash
git clone https://github.com/ricardoquesada/bluepad32.git
cd bluepad32
git submodule update --init
export BLUEPAD32_ROOT=$PWD
```

3. Install required tools:
```bash
sudo apt update
sudo apt install cmake gcc-arm-none-eabi build-essential
# Install picotool for UF2 generation
cd ~/
git clone https://github.com/raspberrypi/picotool.git
cd picotool
mkdir build && cd build
cmake .. && make
sudo make install
```

### Build Process

#### Quick Build (Both Modes)
```bash
cd thumbsup
./tools/build_modes.sh
```

This creates two firmware files:
- `firmware/build/thumbsup.uf2` - Competition mode (Bluetooth)
- `firmware/build_diagnostic/thumbsup.uf2` - Diagnostic mode (WiFi)

#### Building Individual Modes

**Competition Mode (Bluetooth):**
```bash
export PICO_SDK_PATH=/path/to/pico-sdk
export BLUEPAD32_ROOT=/path/to/bluepad32
cd thumbsup/firmware
mkdir build && cd build
cmake .. -DDIAGNOSTIC_MODE=OFF
make -j8
```

**Diagnostic Mode (WiFi):**
```bash
export PICO_SDK_PATH=/path/to/pico-sdk
cd thumbsup/firmware
mkdir build_diagnostic && cd build_diagnostic
cmake .. -DDIAGNOSTIC_MODE=ON
make -j8
```

## Flashing the Firmware

1. Hold the BOOTSEL button on the Pico W
2. Connect the Pico W to your computer via USB
3. Release the BOOTSEL button
4. The Pico will appear as a USB drive
5. Copy `thumbsup.uf2` to the drive
6. The Pico will automatically reboot with the new firmware

## AM32 ESC Configuration

The weapon ESC needs specific configuration for optimal performance:

### Using AM32 Configurator

1. Download AM32 Configurator from [GitHub](https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware)
2. Connect the ESC to your computer using a USB-serial adapter
3. Apply these settings:

```
Motor Direction: Forward
Brake on Stop: OFF
Motor Timing: 16 degrees
Startup Power: Medium
PWM Frequency: 24kHz
Temperature Protection: 80°C
Low Voltage Cutoff: Disabled (managed by robot firmware)
Throttle Calibration: 1000-2000μs
Signal Type: Normal PWM
```

## Safety Procedures

### Pre-Competition Checklist

1. **Battery Check**: Ensure battery voltage > 10V
2. **Connection Test**: Verify gamepad connects automatically
3. **Failsafe Test**: Turn off controller, verify motors stop
4. **Weapon Arm**: Test arm sequence (X+Y hold)
5. **Emergency Stop**: Test L1+R1 disarm

### Operating Procedures

1. Power on robot with weapon ESC disconnected
2. Verify drive functions correctly
3. Connect weapon ESC
4. Arm weapon only when in combat arena
5. Always disarm before handling robot

## Wiring Diagram

### Power Distribution
```
3S LiPo Battery
    |
    +-- Drive ESC Power
    |     |
    |     +-- 5V BEC --> Pico VSYS
    |
    +-- Weapon ESC Power
          |
          +-- 1000μF Capacitor (parallel)
```

### Signal Connections
```
Pico GP2 --> Drive ESC CH1 Signal
Pico GP3 --> Drive ESC CH2 Signal
Pico GP4 --> Weapon ESC Signal
All ESC Grounds --> Pico GND
```

### Battery Monitor
```
Battery + --[10kΩ]--+--[3.3kΩ]-- GND
                    |
                 Pico GP26
```

## Troubleshooting

### Bluetooth Connection Issues
- Ensure controller is in pairing mode (varies by controller type)
- Check STATUS LED for connection state
- Reset Pico if connection fails after 10 seconds
- Bluepad32 automatically handles pairing for supported controllers
- For first-time pairing, controller may need to be in discovery mode

### Motor Not Responding
- Verify PWM signal with oscilloscope/logic analyzer
- Check ESC power and ground connections
- Ensure ESC is calibrated for 1000-2000μs range

### Weapon Won't Arm
- Check battery voltage (must be > 9.6V)
- Verify arm sequence is held for full duration
- Check ARMED LED for feedback

## Development

### Debug Mode

Debug output is enabled by default. Connect via serial terminal (115200 baud) to see:
- Bluepad32 controller detection and pairing status
- Gamepad input values
- System state changes

To disable debug output, remove `DEBUG_MODE=1` from the source files.

### Modifying Parameters

Edit `firmware/include/config.h` to adjust:
- Control deadzones
- Speed limits
- Exponential curves
- Timing constants
- Safety thresholds

### Bluetooth Platform Customization

The Bluepad32 platform implementation is in `firmware/src/bluetooth_platform.c`.
Modify the callbacks to customize:
- Controller mapping
- Input processing
- Special button combinations
- Rumble/LED feedback

## CAD Files

Mechanical design files are hosted on Onshape:
[Link to be provided]

## License

This project is open source hardware and software.
- Software: MIT License
- Hardware: CERN-OHL-S v2

## Safety Warning

This is a combat robot with dangerous spinning weapons. Always:
- Wear safety glasses when operating
- Keep weapon pointed away from people
- Use proper arena/test box
- Follow event safety rules
- Have emergency stop ready

## Support

For issues or questions, please open an issue on GitHub.

---

Built with safety and performance in mind for antweight combat robotics.