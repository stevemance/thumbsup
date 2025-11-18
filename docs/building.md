# Building ThumbsUp Firmware

This guide provides detailed instructions for building the ThumbsUp firmware with Bluepad32 support.

## Prerequisites

### Required Software

1. **Raspberry Pi Pico SDK** (v2.1.0 or later)
2. **Bluepad32** (latest version)
3. **ARM GCC Toolchain**
4. **CMake** (3.13 or later)
5. **Picotool** (for UF2 generation)

### Environment Setup

#### 1. Install Dependencies (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y \
    cmake \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    libstdc++-arm-none-eabi-newlib \
    build-essential \
    git \
    python3
```

#### 2. Install Raspberry Pi Pico SDK

```bash
cd ~/
git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init
export PICO_SDK_PATH=$PWD
echo 'export PICO_SDK_PATH='$PWD >> ~/.bashrc
```

#### 3. Install Bluepad32

```bash
cd ~/
git clone https://github.com/ricardoquesada/bluepad32.git
cd bluepad32
git submodule update --init
cd external/btstack
git apply ../patches/*.patch  # Apply required patches
cd ../..
export BLUEPAD32_ROOT=$PWD
echo 'export BLUEPAD32_ROOT='$PWD >> ~/.bashrc
```

#### 4. Install Picotool

```bash
cd ~/
git clone https://github.com/raspberrypi/picotool.git
cd picotool
mkdir build && cd build
cmake .. -DPICO_SDK_PATH=$PICO_SDK_PATH
make
sudo make install
```

## Building the Firmware

### Quick Build

```bash
cd thumbsup/firmware
mkdir -p build && cd build
cmake .. -DPICO_SDK_PATH=$PICO_SDK_PATH
make -j8
```

### Detailed Build Process

1. **Clone the Repository**
   ```bash
   git clone https://github.com/stevemance/thumbsup.git
   cd thumbsup
   ```

2. **Verify Environment Variables**
   ```bash
   echo $PICO_SDK_PATH  # Should point to pico-sdk directory
   echo $BLUEPAD32_ROOT  # Should point to bluepad32 directory
   ```

3. **Configure CMake**
   ```bash
   cd firmware
   mkdir -p build && cd build
   cmake .. -DPICO_SDK_PATH=$PICO_SDK_PATH
   ```

   Expected output:
   ```
   PICO_SDK_PATH is /home/user/pico-sdk
   Target board (PICO_BOARD) is 'pico_w'.
   BTstack available at /home/user/bluepad32/external/btstack
   Pico W Bluetooth build support available.
   ```

4. **Build the Firmware**
   ```bash
   make -j8  # Use 8 parallel jobs for faster builds
   ```

5. **Output Files**
   The build process generates:
   - `thumbsup.uf2` - Firmware file for flashing
   - `thumbsup.elf` - Debug symbols file
   - `thumbsup.bin` - Binary file
   - `thumbsup.hex` - Hex file

## Build Configuration

### CMake Options

| Option | Description | Default |
|--------|-------------|---------|
| `PICO_SDK_PATH` | Path to Pico SDK | Required |
| `CMAKE_BUILD_TYPE` | Build type (Debug/Release) | Release |
| `PICO_BOARD` | Target board | pico_w |

### Source Files

The firmware consists of:
- `src/main.c` - Main entry point and initialization
- `src/bluetooth_platform.c` - Bluepad32 platform implementation (competition mode)
- `src/motor_control.c` - Motor PWM/DShot control
- `src/drive.c` - Drive mixing and control
- `src/weapon.c` - Weapon motor control
- `src/safety.c` - Safety systems
- `src/status.c` - LED status indicators
- `src/ws2812.c` - SK6812 addressable LED driver
- `src/motor_linearization.c` - Motor response curve compensation
- `src/calibration_mode.c` - Motor calibration system
- `src/trim_mode.c` - Dynamic trim adjustment
- `src/am32_config.c` - AM32 ESC configuration
- `src/dshot.c` - DShot digital protocol
- `src/diagnostic_mode.c` - WiFi diagnostic mode (optional build)
- `src/web_server.c` - Web dashboard (diagnostic mode)

### Configuration Files

- `include/config.h` - System configuration and pin definitions
- `include/sdkconfig.h` - Bluepad32 SDK configuration
- `include/btstack_config.h` - BTstack Bluetooth configuration
- `CMakeLists.txt` - Build system with DIAGNOSTIC_MODE option

## Troubleshooting

### Common Build Errors

#### 1. BLUEPAD32_ROOT Not Found
```
CMake Error: BLUEPAD32_ROOT environment variable is not set
```
**Solution**: Export the BLUEPAD32_ROOT variable:
```bash
export BLUEPAD32_ROOT=/path/to/bluepad32
```

#### 2. BTstack Not Found
```
BTstack available at /path/to/bluepad32/external/btstack
CMake Warning: PICO_BTSTACK_PATH specified but content not present
```
**Solution**: Initialize Bluepad32 submodules:
```bash
cd $BLUEPAD32_ROOT
git submodule update --init --recursive
```

#### 3. Picotool Version Mismatch
```
Incompatible picotool installation found
```
**Solution**: Update picotool to the latest version:
```bash
cd ~/picotool
git pull
cd build
cmake .. && make
sudo make install
```

#### 4. Missing ARM Toolchain
```
The C compiler "arm-none-eabi-gcc" is not able to compile
```
**Solution**: Install the ARM toolchain:
```bash
sudo apt install gcc-arm-none-eabi
```

### Build Verification

To verify your build environment:

```bash
# Check toolchain
arm-none-eabi-gcc --version

# Check CMake
cmake --version

# Check Picotool
picotool version

# Check environment variables
echo $PICO_SDK_PATH
echo $BLUEPAD32_ROOT
```

## Clean Build

To perform a clean build:

```bash
cd firmware/build
rm -rf *
cmake .. -DPICO_SDK_PATH=$PICO_SDK_PATH
make -j8
```

## Development Tips

### Faster Builds
- Use `make -j$(nproc)` to use all CPU cores
- Use ccache for faster rebuilds:
  ```bash
  sudo apt install ccache
  export PATH=/usr/lib/ccache:$PATH
  ```

### Debug Builds
For debug builds with additional output:
```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
make
```

### VSCode Integration
Create `.vscode/settings.json`:
```json
{
    "cmake.environment": {
        "PICO_SDK_PATH": "/path/to/pico-sdk",
        "BLUEPAD32_ROOT": "/path/to/bluepad32"
    },
    "cmake.configureOnOpen": true,
    "C_Cpp.default.configurationProvider": "ms-vscode.cmake-tools"
}
```

## Building Diagnostic Mode

To build the WiFi diagnostic version instead:

```bash
cd firmware
mkdir build-diagnostic
cd build-diagnostic
cmake .. -DDIAGNOSTIC_MODE=ON
make -j8
```

This creates a separate firmware with WiFi access point and web dashboard.

## Next Steps

After building successfully:
1. Flash the firmware to your Pico W
2. Pair your Bluetooth gamepad (competition mode) or connect to WiFi (diagnostic mode)
3. Test the system following [safety procedures](safety_procedures.md)
4. See [User Manual](USER_MANUAL.md) for operation instructions