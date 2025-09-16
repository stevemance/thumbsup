# AM32 ESC Programming via Pico

The antweight robot firmware includes built-in AM32 ESC configuration capability, eliminating the need for separate programming hardware.

## How It Works

The AM32 ESC can be programmed through its PWM signal line using a serial protocol. The Pico W can switch the weapon PWM pin (GP4) between:
- **Normal PWM mode**: For motor control during operation
- **UART mode**: For ESC configuration and programming

## Configuration Methods

### Method 1: Built-in Configuration Mode

1. **Enter Config Mode**:
   - Hold the safety button (GP8) while powering on the Pico
   - The serial terminal will show the configuration menu

2. **Available Options**:
   - **C**: Configure ESC with weapon defaults
   - **P**: Passthrough mode for external configurator
   - **T**: Throttle calibration
   - **D**: Apply default settings

3. **Example Session**:
   ```
   =================================
     AM32 Configuration Mode
   =================================

   Options:
   1. Press 'C' to configure ESC
   2. Press 'P' for passthrough mode
   3. Press 'T' for throttle calibration
   4. Press 'D' to apply defaults
   5. Press any other key to exit

   > C
   Configuring AM32 ESC with weapon defaults...
   Configuration complete!
   ```

### Method 2: Python Configuration Tool

Use the included Python tool for more control:

```bash
cd thumbsup/tools

# Interactive mode
./am32_config.py --interactive

# Apply weapon defaults
./am32_config.py --defaults --save

# Read current settings
./am32_config.py --read

# Calibrate throttle
./am32_config.py --calibrate
```

### Method 3: Passthrough Mode

For use with the official AM32 Configurator:

1. Enter passthrough mode on the Pico (hold safety button, press 'P')
2. Connect AM32 Configurator to the Pico's USB serial port
3. Configure as normal through the GUI
4. Press ESC key to exit passthrough mode

## Default Weapon Configuration

The firmware automatically applies these optimal settings for weapon operation:

| Parameter | Value | Reason |
|-----------|-------|---------|
| Motor Direction | Forward | Unidirectional weapon |
| Bidirectional | OFF | Weapon only spins one way |
| Brake on Stop | OFF | Let weapon coast to stop |
| Startup Power | 6/10 | Medium-high for quick spin-up |
| Motor Timing | 16° | Optimal for F2822 motor |
| PWM Frequency | 24kHz | Smooth operation |
| Temperature Limit | 80°C | Protect ESC |
| Current Limit | 40A | Within ESC rating |
| Throttle Range | 1000-2000μs | Standard servo signal |
| Demag Compensation | High | Handle heavy weapon loads |

## Wiring for Programming

The same 3-wire connection used for normal operation is used for programming:

```
Pico GP4 ←→ ESC Signal (White/Yellow)
Pico GND ←→ ESC Ground (Black/Brown)
ESC Power ←→ 3S Battery (separate connection)
```

No additional wiring needed!

## Programming Sequence

### First-Time Setup

1. **Connect Hardware**:
   ```
   - Wire ESC signal to Pico GP4
   - Connect grounds
   - Power ESC from battery
   - Connect Pico via USB
   ```

2. **Flash Pico Firmware**:
   ```bash
   cd thumbsup/tools
   ./build.sh
   ./flash.sh --auto
   ```

3. **Configure ESC**:
   ```bash
   # Open serial monitor
   ./monitor.py --auto

   # Hold safety button and reset Pico
   # Select 'D' for defaults or 'C' for full config
   ```

4. **Calibrate Throttle**:
   ```bash
   # In config mode, select 'T'
   # Follow on-screen prompts
   ```

### Field Adjustments

Make quick changes without a computer:

1. Power on with safety button held
2. Use gamepad buttons to select options:
   - A button: Apply defaults
   - B button: Calibrate throttle
   - X button: Increase timing
   - Y button: Decrease timing

## Troubleshooting

### ESC Not Responding

1. **Check Wiring**:
   - Signal and ground connected
   - ESC has power
   - Correct pin (GP4)

2. **Verify Protocol**:
   - ESC must support AM32 serial protocol
   - Firmware version 2.0+ recommended

3. **Reset ESC**:
   - Power cycle ESC
   - Try entering bootloader mode

### Configuration Not Saving

1. **Save to EEPROM**:
   - Always select save option after changes
   - Wait for confirmation

2. **Power Cycle**:
   - Turn off ESC after saving
   - Settings load on next power-up

### Communication Errors

1. **Signal Integrity**:
   - Keep signal wire short (<15cm)
   - Away from motor wires
   - Good ground connection

2. **Timing Issues**:
   - Ensure no motors running
   - Stable power supply
   - No Bluetooth interference

## Advanced Features

### Custom Configuration Files

Create JSON configuration files:

```json
{
  "motor_direction": "forward",
  "bidirectional": false,
  "brake_on_stop": false,
  "startup_power": 7,
  "motor_timing": 18,
  "pwm_frequency": 48,
  "temperature_limit": 85,
  "current_limit": 35
}
```

Apply with:
```bash
./am32_config.py --write my_config.json --save
```

### Telemetry Reading

When telemetry is enabled, read ESC data:
- Temperature
- Current draw
- RPM
- Voltage

Access via serial monitor during operation.

### Firmware Updates

The Pico can also flash new AM32 firmware:

1. Download AM32 firmware .hex file
2. Enter bootloader mode (config menu option)
3. Use flash tool to upload firmware

## Safety Notes

⚠️ **WARNING**: Always configure with motor/weapon disconnected!

- ESC may spin motor during configuration
- Throttle calibration requires full throttle
- Some settings cause immediate motor start
- Keep clear of weapon path

## Benefits of Integrated Programming

1. **No Extra Hardware**: No need for USB-Serial adapter or STLink
2. **Field Programmable**: Adjust settings at competition
3. **Single Connection**: Same wiring for operation and programming
4. **Automated Setup**: One-button weapon configuration
5. **Safety Integration**: Config mode prevents accidental arming

## Quick Reference

| Action | Button/Key | Mode |
|--------|------------|------|
| Enter Config | Hold Safety + Power | Boot |
| Apply Defaults | D | Config Menu |
| Calibrate | T | Config Menu |
| Passthrough | P | Config Menu |
| Save Settings | S | After Changes |
| Exit | ESC | Passthrough |

---

With integrated AM32 programming, your weapon ESC is always just a button press away from being perfectly configured!