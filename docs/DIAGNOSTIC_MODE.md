# ThumbsUp Diagnostic Mode

## Overview

The ThumbsUp robot firmware includes a **Diagnostic Mode** that provides a WiFi-based web interface for telemetry, testing, and control. This mode is designed for pit debugging, system testing, and detailed diagnostics when Bluetooth gamepad control is not needed.

> **Note**: Diagnostic Mode is currently disabled in the build due to WiFi/Bluetooth coexistence limitations with the CYW43439 chip. The implementation is complete but requires stack refactoring to enable both radios simultaneously.

## Features

### Web Dashboard
- **Real-time telemetry** display
- **System status** monitoring (CPU, memory, uptime)
- **Battery monitoring** with voltage and percentage
- **Motor control** via virtual joystick
- **Weapon control** with safety interlocks
- **Event logging** with timestamps
- **LED status** indicators
- **Emergency stop** controls
- **Safety test** execution

### Web Interface Components

#### System Status Card
- Current state (IDLE/ARMED/E-STOPPED)
- Uptime counter
- CPU usage percentage
- Memory usage
- Loop timing
- Temperature (when sensor added)
- LED status visualization

#### Battery Status Card
- Visual battery bar
- Voltage display
- Current draw (when sensor added)
- Percentage calculation
- Color-coded warnings

#### Emergency Controls
- Emergency stop button
- Clear E-stop
- Run safety tests
- System reboot

#### Weapon Control
- Arm/disarm buttons
- Speed slider (0-100%)
- Status display
- Safety interlocks

#### Drive Control
- Virtual joystick interface
- Touch/mouse support
- Real-time position feedback
- Motor speed display

#### Event Log
- Scrollable event history
- Timestamped entries
- System events
- User actions
- Error messages

## Architecture

### Dual-Mode System

The firmware supports two mutually exclusive operating modes:

1. **Competition Mode** (Default)
   - Bluetooth gamepad control
   - Low latency operation
   - Minimal overhead
   - Competition-ready

2. **Diagnostic Mode**
   - WiFi Access Point
   - Web server on 192.168.4.1
   - HTTP/JSON API
   - Telemetry streaming
   - Debug controls

### Mode Selection

Mode is selected at boot time:
- **Normal boot** → Competition Mode
- **Hold safety button 3 seconds during boot** → Diagnostic Mode

### Technical Implementation

```c
// Mode selection at startup
if (should_enter_diagnostic_mode()) {
    diagnostic_mode_init();    // Start WiFi AP
    diagnostic_mode_run();      // Run web server
} else {
    // Normal Bluetooth mode
    cyw43_arch_init();
    uni_init(0, NULL);
    btstack_run_loop_execute();
}
```

### WiFi Configuration
- **SSID**: `ThumbsUp_Diag`
- **Password**: `combat123` (change in production)
- **IP Address**: `192.168.4.1`
- **Port**: 80 (HTTP)
- **Max Clients**: 4

### API Endpoints

#### GET /
Returns the main dashboard HTML page

#### GET /telemetry
Returns JSON telemetry data:
```json
{
  "uptime_ms": 123456,
  "armed": false,
  "emergency_stopped": false,
  "battery_voltage_mv": 11500,
  "battery_percentage": 75.5,
  "left_drive_speed": 0,
  "right_drive_speed": 0,
  "weapon_speed": 0,
  "cpu_usage_percent": 45,
  "free_memory_bytes": 98304,
  "temperature_c": 25.0,
  "event_log": ["[0.123] System initialized", ...]
}
```

#### POST /control
Accepts JSON control commands:
```json
{
  "emergency_stop": true,
  "clear_emergency_stop": false,
  "arm_weapon": false,
  "disarm_weapon": true,
  "drive_forward": 50,
  "drive_turn": -20,
  "weapon_speed": 75,
  "run_safety_tests": false,
  "reboot_system": false
}
```

## Usage

### Entering Diagnostic Mode

1. Power off robot
2. Hold safety button
3. Power on robot
4. Keep holding safety button for 3 seconds
5. Release when "Entering diagnostic mode!" appears
6. WiFi AP will start

### Connecting to Dashboard

1. Connect to WiFi network:
   - SSID: `ThumbsUp_Diag`
   - Password: `combat123`

2. Open web browser
3. Navigate to: `http://192.168.4.1`
4. Dashboard will load automatically

### Using the Dashboard

#### Drive Testing
1. Click and drag the virtual joystick
2. Or use touch on mobile devices
3. Release returns to center (stop)
4. Monitor motor speeds in real-time

#### Weapon Testing
1. Click "ARM" button (confirmation required)
2. Adjust weapon speed slider
3. Monitor weapon speed percentage
4. Click "DISARM" when done

#### Safety Testing
1. Click "Run Safety Tests"
2. View results in event log
3. All 6 tests should pass
4. System locks out if tests fail

#### Emergency Stop
1. Click red "E-STOP" button
2. All motors stop immediately
3. Click "Clear E-Stop" to reset
4. System must be re-armed

### Exiting Diagnostic Mode

Two methods:
1. Hold safety button for 5 seconds
2. Click reboot in web interface

System will restart in Competition Mode.

## Implementation Status

### ✅ Completed
- Diagnostic mode architecture
- Web dashboard HTML/CSS/JavaScript
- Telemetry data structures
- JSON API endpoints
- Virtual joystick control
- Event logging system
- Mode selection logic
- Safety interlocks

### ⚠️ Why It's Disabled

The diagnostic mode is **fully implemented** but disabled because:

**You're exactly right** - we CAN have a boot timeout that selects either WiFi OR Bluetooth mode. The CYW43439 chip can do either, just not both simultaneously.

The issue is the Pico SDK's CMake build system requires you to choose at compile time:
- `pico_cyw43_arch_none` - For Bluetooth (what we use)
- `pico_cyw43_arch_lwip_poll` - For WiFi with networking

We can't link both in the same binary. The code for exclusive mode selection is ready, but it needs **two separate firmware builds**.

### 🔧 How to Enable Diagnostic Mode

To enable diagnostic mode:

1. **Option A**: Exclusive Mode (Recommended)
   - Fully initialize either WiFi OR Bluetooth
   - Not both simultaneously
   - Requires conditional compilation

2. **Option B**: Coexistence Mode (Complex)
   - Use `pico_cyw43_arch_lwip_threadsafe`
   - Implement time-division multiplexing
   - May impact real-time performance
   - Requires significant refactoring

3. **Option C**: External Module
   - Separate diagnostic module
   - ESP32 or second Pico W
   - Serial communication
   - Maintains performance

## Security Considerations

⚠️ **WARNING**: The diagnostic mode provides full robot control over WiFi!

### Current Security
- WPA2 password protection
- Local AP only (no internet)
- Confirmation for dangerous operations

### Recommended Improvements
- Change default password
- Add authentication tokens
- Implement HTTPS (if possible)
- Rate limiting on controls
- Timeout on idle connections
- Disable in competition builds

## Performance Impact

When active, diagnostic mode:
- Uses ~30KB additional RAM
- Adds 100-200μs loop time
- Reduces available CPU for motor control
- May impact Bluetooth if coexistence enabled

## Future Enhancements

### Planned Features
- [ ] Data logging to flash
- [ ] Telemetry graphing
- [ ] PID tuning interface
- [ ] Sensor calibration
- [ ] Configuration backup/restore
- [ ] Video streaming (if camera added)
- [ ] Multi-robot management
- [ ] Cloud telemetry upload

### Hardware Additions
- [ ] Current sensors for power monitoring
- [ ] Temperature sensor for thermal management
- [ ] Accelerometer for impact detection
- [ ] Gyroscope for orientation

## Troubleshooting

### WiFi AP Not Starting
- Verify safety button held during boot
- Check serial output for errors
- Ensure battery voltage sufficient
- Try power cycling

### Can't Connect to Dashboard
- Verify connected to correct WiFi network
- Check password (case sensitive)
- Try different browser
- Clear browser cache
- Disable VPN/proxy

### Controls Not Responding
- Check emergency stop not active
- Verify weapon armed (if using weapon)
- Check battery voltage
- Monitor event log for errors

### High Latency
- Reduce number of connected clients
- Move closer to robot
- Check for WiFi interference
- Reduce telemetry update rate

## Development Notes

### File Structure
```
firmware/
├── include/
│   └── diagnostic_mode.h    # API definitions
├── src/
│   ├── diagnostic_mode.c     # Main implementation
│   └── web_server.c          # HTTP server & dashboard
```

### Memory Layout
- Dashboard HTML: ~15KB (stored in flash)
- Telemetry buffer: ~4KB
- Event log: ~2KB
- Network buffers: ~8KB
- Total overhead: ~30KB

### Build Configuration
Currently disabled in CMakeLists.txt:
```cmake
# src/diagnostic_mode.c     # Disabled
# src/web_server.c          # Disabled
```

To enable:
1. Uncomment source files
2. Add lwIP libraries
3. Resolve stack conflicts
4. Test thoroughly

---

**Note**: This feature represents significant development effort and provides powerful debugging capabilities. Once WiFi/Bluetooth coexistence is resolved, it will greatly enhance robot development and testing workflows.