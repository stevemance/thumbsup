# Bluepad32 Integration Guide

## Overview

ThumbsUp uses Bluepad32 to provide universal Bluetooth gamepad support. This guide explains how the integration works and how to customize it.

## Architecture

```
Main Program (main.c)
    ↓
Bluepad32 Init (uni_init)
    ↓
Platform Registration (bluetooth_platform.c)
    ↓
BTstack Event Loop (runs forever)
    ↓
Controller Events → Platform Callbacks → Robot Control
```

## Platform Implementation

The Bluepad32 platform is implemented in `firmware/src/bluetooth_platform.c`.

### Key Callbacks

#### Controller Data Handler
```c
static void thumbsup_platform_on_controller_data(
    uni_hid_device_t* d,
    uni_controller_t* ctl
) {
    // Called when controller sends data
    // Process gamepad inputs here
}
```

#### Connection Events
```c
static void thumbsup_platform_on_device_connected(uni_hid_device_t* d) {
    // Controller connected
}

static void thumbsup_platform_on_device_disconnected(uni_hid_device_t* d) {
    // Controller disconnected - trigger failsafe
}
```

## Supported Controllers

Bluepad32 supports a wide range of controllers:

| Controller | Status | Notes |
|------------|--------|-------|
| Xbox One/Series | ✅ Tested | Full support including rumble |
| PlayStation 3 | ✅ Tested | Classic Bluetooth only |
| PlayStation 4 | ✅ Tested | Full support including lightbar |
| PlayStation 5 | ✅ Tested | Full support including haptics |
| Switch Pro | ✅ Tested | Full support |
| Switch JoyCons | ✅ Supported | Single or paired |
| 8BitDo | ✅ Tested | All models supported |
| Steam Controller | ✅ Supported | Requires pairing mode |
| Stadia | ✅ Supported | Via Bluetooth mode |
| Generic HID | ✅ Supported | Basic button/axis support |

## Control Mapping

Default mapping in `bluetooth_platform.c`:

```c
// Left stick - Drive control
int8_t forward = gp->axis_y / 4;  // Scale to -128 to 127
int8_t turn = gp->axis_x / 4;

// Right stick - Weapon control
int8_t weapon_speed = gp->axis_ry / 4;

// Buttons
bool arm_weapon = (gp->buttons & BUTTON_X) && (gp->buttons & BUTTON_Y);
bool emergency_stop = (gp->buttons & BUTTON_SHOULDER_L) &&
                     (gp->buttons & BUTTON_SHOULDER_R);
```

## Customization

### Adding Custom Button Combinations

```c
// In thumbsup_platform_on_controller_data()
if ((gp->buttons & BUTTON_A) && (gp->buttons & BUTTON_B)) {
    // Custom action
    toggle_special_mode();
}
```

### Implementing Rumble Feedback

```c
// Trigger rumble on weapon armed
if (weapon_armed && d->report_parser.play_dual_rumble) {
    d->report_parser.play_dual_rumble(
        d,
        0,      // delay ms
        100,    // duration ms
        64,     // weak magnitude (0-255)
        128     // strong magnitude (0-255)
    );
}
```

### Controller-Specific Features

```c
// Set PlayStation lightbar color
if (d->report_parser.set_lightbar_color) {
    d->report_parser.set_lightbar_color(d, 255, 0, 0); // Red
}

// Set player LEDs (Xbox/Switch)
if (d->report_parser.set_player_leds) {
    d->report_parser.set_player_leds(d, 0x01); // Player 1
}
```

## Pairing Process

### First-Time Pairing

1. Power on the Pico W - STATUS LED will blink
2. Put controller in pairing mode:
   - **Xbox**: Hold Xbox button + Pair button
   - **PlayStation**: Hold PS + Share buttons
   - **Switch Pro**: Hold Sync button
   - **8BitDo**: Hold Select + Start
3. Controller will auto-connect when found
4. STATUS LED turns solid when connected

### Auto-Reconnection

Once paired, controllers automatically reconnect when:
- Robot powers on
- Controller turns on
- After signal loss recovery

## Debugging

### Enable Debug Output

Debug messages are sent via USB serial (115200 baud):

```c
// In bluetooth_platform.c
logi("Controller connected: %s\n", d->name);
logi("Gamepad data: X=%d Y=%d\n", gp->axis_x, gp->axis_y);
```

### Monitor Connection Status

```bash
# Connect to USB serial
screen /dev/ttyACM0 115200

# Expected output:
ThumbsUp Platform: init()
Bluetooth scanning started
Device discovered: Xbox Wireless Controller
Device connected: 0x12345678
Controller ready
Gamepad: LX:0 LY:0 RX:0 RY:0 Buttons:0x0000
```

## Troubleshooting

### Controller Not Connecting

1. **Check Bluepad32 is initialized**:
   ```c
   // main.c should have:
   uni_platform_set_custom(get_my_platform());
   uni_init(0, NULL);
   ```

2. **Verify platform registration**:
   ```c
   // bluetooth_platform.c must export:
   struct uni_platform* get_my_platform(void);
   ```

3. **Clear paired devices**:
   Hold BOOTSEL while powering on to clear all pairings

### Delayed Response

- Reduce debug output frequency
- Check for blocking operations in callbacks
- Ensure callbacks complete quickly (<10ms)

### Specific Controller Issues

#### Xbox Controllers
- May need firmware update via Xbox
- Try wired pairing first on Xbox/PC

#### PlayStation Controllers
- PS3: Needs special pairing tool on PC first
- PS4/PS5: Reset controller with pin in small hole

#### Switch Controllers
- Update controller firmware via Switch
- JoyCons: Pair individually then together

## Performance Optimization

### Reduce Latency

```c
// Increase Bluetooth polling rate (in btstack_config.h)
#define HCI_DEFAULT_CONNECTION_INTERVAL_MIN 6  // 7.5ms
#define HCI_DEFAULT_CONNECTION_INTERVAL_MAX 12 // 15ms
```

### Battery Life

```c
// Reduce scan window when not connected
uni_bt_set_gap_inquiry_length(0x08);  // Shorter scan
uni_bt_set_gap_max_periodic_length(0x800); // Longer sleep
```

## Safety Considerations

Always implement failsafes in the platform callbacks:

```c
static void thumbsup_platform_on_device_disconnected(uni_hid_device_t* d) {
    // CRITICAL: Stop all motors immediately
    emergency_stop();
    weapon_disarm();
    drive_stop();

    // Set visual indicator
    status_set_error(STATUS_ERROR_DISCONNECTED);
}
```

## Further Resources

- [Bluepad32 Documentation](https://github.com/ricardoquesada/bluepad32)
- [BTstack Documentation](https://github.com/bluekitchen/btstack)
- [Supported Controllers List](https://github.com/ricardoquesada/bluepad32/blob/main/docs/supported_gamepads.md)