#!/bin/bash

# Build script for ThumbsUp Robot firmware - Both modes
# This creates two separate binaries: one for competition (Bluetooth) and one for diagnostic (WiFi)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
FIRMWARE_DIR="$PROJECT_ROOT/firmware"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ThumbsUp Robot Dual Mode Build Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check for Pico SDK
if [ -z "$PICO_SDK_PATH" ]; then
    if [ -d "$HOME/pico/pico-sdk" ]; then
        export PICO_SDK_PATH="$HOME/pico/pico-sdk"
    else
        echo -e "${RED}Error: PICO_SDK_PATH not set${NC}"
        exit 1
    fi
fi

# Parse arguments
BUILD_COMP=1
BUILD_DIAG=1
CLEAN=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --competition-only)
            BUILD_DIAG=0
            shift
            ;;
        --diagnostic-only)
            BUILD_COMP=0
            shift
            ;;
        --clean)
            CLEAN=1
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --competition-only  Build only competition mode (Bluetooth)"
            echo "  --diagnostic-only   Build only diagnostic mode (WiFi)"
            echo "  --clean            Clean build directories before building"
            echo "  --help             Show this help message"
            echo ""
            echo "By default, both modes are built."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Function to build a mode
build_mode() {
    local MODE_NAME=$1
    local BUILD_DIR=$2
    local CMAKE_ARGS=$3

    echo -e "\n${BLUE}Building $MODE_NAME...${NC}"

    if [ $CLEAN -eq 1 ]; then
        echo "Cleaning $BUILD_DIR..."
        rm -rf "$BUILD_DIR"
    fi

    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"

    # Configure
    if [ ! -f "Makefile" ] || [ $CLEAN -eq 1 ]; then
        cmake $CMAKE_ARGS .. || {
            echo -e "${RED}CMake configuration failed for $MODE_NAME${NC}"
            return 1
        }
    fi

    # Build
    make -j$(nproc) || {
        echo -e "${RED}Build failed for $MODE_NAME${NC}"
        return 1
    }

    if [ -f "thumbsup.uf2" ]; then
        SIZE=$(du -h "thumbsup.uf2" | cut -f1)
        echo -e "${GREEN}✓ $MODE_NAME built successfully (${SIZE})${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to create UF2 for $MODE_NAME${NC}"
        return 1
    fi
}

# Build competition mode
if [ $BUILD_COMP -eq 1 ]; then
    # Check for Bluepad32 (only needed for competition mode)
    if [ -z "$BLUEPAD32_ROOT" ]; then
        if [ -d "$HOME/bluepad32" ]; then
            export BLUEPAD32_ROOT="$HOME/bluepad32"
        elif [ -d "$HOME/playbox/bluepad32" ]; then
            export BLUEPAD32_ROOT="$HOME/playbox/bluepad32"
        else
            echo -e "${RED}Error: BLUEPAD32_ROOT not set for competition mode${NC}"
            echo "Please install Bluepad32 or set BLUEPAD32_ROOT"
            exit 1
        fi
    fi

    build_mode "COMPETITION MODE (Bluetooth)" \
               "$FIRMWARE_DIR/build" \
               "-DPICO_SDK_PATH=$PICO_SDK_PATH -DDIAGNOSTIC_MODE=OFF"
fi

# Build diagnostic mode
if [ $BUILD_DIAG -eq 1 ]; then
    build_mode "DIAGNOSTIC MODE (WiFi)" \
               "$FIRMWARE_DIR/build_diagnostic" \
               "-DPICO_SDK_PATH=$PICO_SDK_PATH -DDIAGNOSTIC_MODE=ON"
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Summary${NC}"
echo -e "${GREEN}========================================${NC}"

if [ $BUILD_COMP -eq 1 ] && [ -f "$FIRMWARE_DIR/build/thumbsup.uf2" ]; then
    echo -e "${GREEN}Competition Mode:${NC} $FIRMWARE_DIR/build/thumbsup.uf2"
    echo "  - Bluetooth gamepad control"
    echo "  - Full safety tests at startup"
    echo "  - Combat ready"
fi

if [ $BUILD_DIAG -eq 1 ] && [ -f "$FIRMWARE_DIR/build_diagnostic/thumbsup.uf2" ]; then
    echo -e "${BLUE}Diagnostic Mode:${NC} $FIRMWARE_DIR/build_diagnostic/thumbsup.uf2"
    echo "  - WiFi AP: ThumbsUp_Diag"
    echo "  - Password: combat123"
    echo "  - Web interface: http://192.168.4.1"
fi

echo ""
echo "To flash: Hold BOOTSEL, connect USB, copy appropriate .uf2 file to RPI-RP2 drive"
echo ""