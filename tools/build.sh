#!/bin/bash

# Build script for ThumbsUp Robot firmware

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
FIRMWARE_DIR="$PROJECT_ROOT/firmware"
BUILD_DIR="$FIRMWARE_DIR/build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}  ThumbsUp Robot Build Script${NC}"
echo -e "${GREEN}==================================${NC}"

# Check for Pico SDK
if [ -z "$PICO_SDK_PATH" ]; then
    echo -e "${YELLOW}Warning: PICO_SDK_PATH not set${NC}"
    echo "Looking for Pico SDK in common locations..."

    if [ -d "$HOME/pico/pico-sdk" ]; then
        export PICO_SDK_PATH="$HOME/pico/pico-sdk"
        echo -e "${GREEN}Found Pico SDK at $PICO_SDK_PATH${NC}"
    elif [ -d "/usr/share/pico-sdk" ]; then
        export PICO_SDK_PATH="/usr/share/pico-sdk"
        echo -e "${GREEN}Found Pico SDK at $PICO_SDK_PATH${NC}"
    else
        echo -e "${RED}Error: Could not find Pico SDK${NC}"
        echo "Please install the Pico SDK and set PICO_SDK_PATH"
        exit 1
    fi
fi

# Check for Bluepad32
if [ -z "$BLUEPAD32_ROOT" ]; then
    echo -e "${YELLOW}Warning: BLUEPAD32_ROOT not set${NC}"
    echo "Looking for Bluepad32 in common locations..."

    if [ -d "$HOME/bluepad32" ]; then
        export BLUEPAD32_ROOT="$HOME/bluepad32"
        echo -e "${GREEN}Found Bluepad32 at $BLUEPAD32_ROOT${NC}"
    elif [ -d "$HOME/pico/bluepad32" ]; then
        export BLUEPAD32_ROOT="$HOME/pico/bluepad32"
        echo -e "${GREEN}Found Bluepad32 at $BLUEPAD32_ROOT${NC}"
    elif [ -d "/opt/bluepad32" ]; then
        export BLUEPAD32_ROOT="/opt/bluepad32"
        echo -e "${GREEN}Found Bluepad32 at $BLUEPAD32_ROOT${NC}"
    else
        echo -e "${RED}Error: Could not find Bluepad32${NC}"
        echo "Please install Bluepad32 and set BLUEPAD32_ROOT"
        echo "git clone https://github.com/ricardoquesada/bluepad32.git"
        echo "cd bluepad32 && git submodule update --init"
        exit 1
    fi
fi

# Check for required tools
echo "Checking for required tools..."

if ! command -v cmake &> /dev/null; then
    echo -e "${RED}Error: cmake not found${NC}"
    echo "Install with: sudo apt install cmake"
    exit 1
fi

if ! command -v arm-none-eabi-gcc &> /dev/null; then
    echo -e "${RED}Error: arm-none-eabi-gcc not found${NC}"
    echo "Install with: sudo apt install gcc-arm-none-eabi"
    exit 1
fi

echo -e "${GREEN}All required tools found${NC}"

# Parse arguments
CLEAN=0
DEBUG=0
VERBOSE=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=1
            shift
            ;;
        --debug)
            DEBUG=1
            shift
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --clean    Clean build directory before building"
            echo "  --debug    Build with debug symbols and output"
            echo "  --verbose  Show verbose build output"
            echo "  --help     Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Clean if requested
if [ $CLEAN -eq 1 ]; then
    echo -e "${YELLOW}Cleaning build directory...${NC}"
    rm -rf "$BUILD_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure with CMake
echo -e "${GREEN}Configuring with CMake...${NC}"

CMAKE_ARGS=""
if [ $DEBUG -eq 1 ]; then
    CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_BUILD_TYPE=Debug"
else
    CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_BUILD_TYPE=Release"
fi

cmake $CMAKE_ARGS ..

# Build
echo -e "${GREEN}Building firmware...${NC}"

if [ $VERBOSE -eq 1 ]; then
    make VERBOSE=1 -j$(nproc)
else
    make -j$(nproc)
fi

# Check if build succeeded
if [ -f "$BUILD_DIR/thumbsup.uf2" ]; then
    echo -e "${GREEN}==================================${NC}"
    echo -e "${GREEN}  Build Successful!${NC}"
    echo -e "${GREEN}==================================${NC}"
    echo ""
    echo "Firmware file: $BUILD_DIR/thumbsup.uf2"
    echo ""
    echo "To flash the firmware:"
    echo "1. Hold BOOTSEL button on Pico W"
    echo "2. Connect Pico W to computer via USB"
    echo "3. Release BOOTSEL button"
    echo "4. Copy thumbsup.uf2 to the RPI-RP2 drive"
    echo ""

    # Show file size
    SIZE=$(du -h "$BUILD_DIR/thumbsup.uf2" | cut -f1)
    echo "Firmware size: $SIZE"
else
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi