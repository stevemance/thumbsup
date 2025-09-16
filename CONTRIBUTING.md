# Contributing to ThumbsUp Robot

Thank you for your interest in contributing to the ThumbsUp antweight robot project!

## How to Contribute

### Reporting Issues

- Check existing issues before creating a new one
- Include system information (OS, Pico SDK version, etc.)
- Provide clear reproduction steps
- Include relevant logs or error messages

### Suggesting Features

- Open an issue with the "enhancement" label
- Describe the use case and benefits
- Consider safety implications for combat robots

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Follow coding standards**:
   - Use consistent indentation (4 spaces for C)
   - Comment complex logic
   - Keep functions focused and small
   - Ensure integer math for embedded efficiency

4. **Test thoroughly**:
   - Test on actual hardware when possible
   - Verify safety features still work
   - Check failsafe operation

5. **Commit with clear messages**:
   ```bash
   git commit -m "component: Brief description

   Longer explanation if needed"
   ```

6. **Submit a pull request**:
   - Reference any related issues
   - Describe testing performed
   - Note any safety considerations

## Development Setup

### Prerequisites

```bash
# Install Pico SDK
git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init
export PICO_SDK_PATH=$PWD

# Install Bluepad32
git clone https://github.com/ricardoquesada/bluepad32.git
cd bluepad32
git submodule update --init
cd external/btstack
git apply ../patches/*.patch
cd ../..
export BLUEPAD32_ROOT=$PWD

# Install build tools
sudo apt install cmake gcc-arm-none-eabi build-essential picotool
```

### Building

```bash
cd firmware
mkdir build && cd build
cmake .. -DPICO_SDK_PATH=$PICO_SDK_PATH
make -j$(nproc)
```

See [Building Documentation](docs/building.md) for detailed instructions.

### Testing

- Always test with motor disconnected first
- Verify failsafe triggers correctly
- Test Bluetooth disconnection handling with Bluepad32
- Check battery monitoring accuracy
- Test multiple controller types (Xbox, PlayStation, Switch Pro)
- Verify controller auto-reconnection

## Code Style Guide

### C Code

```c
// Function names: snake_case
void motor_control_init(void);

// Constants: UPPER_CASE
#define MAX_SPEED 100

// Structs: snake_case with _t suffix
typedef struct {
    uint8_t speed;
    bool enabled;
} motor_state_t;

// Bluepad32 platform callbacks
void thumbsup_platform_on_controller_data(uni_hid_device_t* d, uni_controller_t* ctl) {
    // Process gamepad data
}

// Always check return values
if (!safety_check()) {
    handle_error();
}
```

### Python Code

```python
# Follow PEP 8
def configure_esc(port: str, settings: dict) -> bool:
    """Configure AM32 ESC with given settings."""
    pass
```

## Safety Guidelines

⚠️ **Critical**: All contributions must maintain or improve safety

- Never bypass failsafes
- Always default to safe states
- Test emergency stop functionality
- Document any safety implications

## Areas Needing Help

- [ ] IMU integration for self-righting
- [ ] Telemetry dashboard
- [x] Alternative controller support (Completed with Bluepad32)
- [ ] Power consumption optimization
- [ ] Unit test framework
- [ ] Simulator for testing without hardware
- [ ] Custom controller profiles in Bluepad32
- [ ] Rumble feedback implementation
- [ ] Controller battery monitoring

## Questions?

Open an issue with the "question" label or reach out in discussions.

Thank you for helping make combat robotics safer and more accessible!