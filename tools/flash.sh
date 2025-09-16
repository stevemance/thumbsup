#!/bin/bash

# Flash script for ThumbsUp Robot firmware

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
FIRMWARE_DIR="$PROJECT_ROOT/firmware"
BUILD_DIR="$FIRMWARE_DIR/build"
FIRMWARE_FILE="$BUILD_DIR/thumbsup.uf2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}  ThumbsUp Robot Flash Tool${NC}"
echo -e "${GREEN}==================================${NC}"

# Check if firmware exists
if [ ! -f "$FIRMWARE_FILE" ]; then
    echo -e "${RED}Error: Firmware file not found!${NC}"
    echo "Expected location: $FIRMWARE_FILE"
    echo ""
    echo "Please build the firmware first:"
    echo "  $SCRIPT_DIR/build.sh"
    exit 1
fi

# Parse arguments
AUTO=0
DEVICE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto)
            AUTO=1
            shift
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --auto         Automatically detect and flash Pico"
            echo "  --device PATH  Specify device path (e.g., /media/user/RPI-RP2)"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to detect Pico in bootloader mode
detect_pico() {
    # Common mount points for Pico in bootloader mode
    local MOUNT_POINTS=(
        "/media/$USER/RPI-RP2"
        "/mnt/pico"
        "/Volumes/RPI-RP2"
        "/run/media/$USER/RPI-RP2"
    )

    for mount in "${MOUNT_POINTS[@]}"; do
        if [ -d "$mount" ] && [ -f "$mount/INFO_UF2.TXT" ]; then
            echo "$mount"
            return 0
        fi
    done

    # Try to find via mount command
    local mounted=$(mount | grep "RPI-RP2" | awk '{print $3}')
    if [ -n "$mounted" ]; then
        echo "$mounted"
        return 0
    fi

    return 1
}

# Function to wait for Pico
wait_for_pico() {
    echo -e "${YELLOW}Waiting for Raspberry Pi Pico...${NC}"
    echo "1. Hold the BOOTSEL button on your Pico W"
    echo "2. Connect the Pico W to your computer via USB"
    echo "3. Release the BOOTSEL button"
    echo ""

    local count=0
    while [ $count -lt 30 ]; do
        if PICO_PATH=$(detect_pico); then
            echo -e "${GREEN}Found Pico at: $PICO_PATH${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        count=$((count + 1))
    done

    echo ""
    return 1
}

# Main flashing logic
if [ -n "$DEVICE" ]; then
    # Use specified device
    if [ ! -d "$DEVICE" ]; then
        echo -e "${RED}Error: Device path does not exist: $DEVICE${NC}"
        exit 1
    fi
    PICO_PATH="$DEVICE"
elif [ $AUTO -eq 1 ]; then
    # Auto-detect mode
    if ! PICO_PATH=$(detect_pico); then
        if ! wait_for_pico; then
            echo -e "${RED}Error: Timeout waiting for Pico${NC}"
            exit 1
        fi
        PICO_PATH=$(detect_pico)
    fi
else
    # Interactive mode
    if PICO_PATH=$(detect_pico); then
        echo -e "${GREEN}Found Pico at: $PICO_PATH${NC}"
    else
        if ! wait_for_pico; then
            echo -e "${RED}Error: Could not detect Pico${NC}"
            echo ""
            echo "Manual flashing instructions:"
            echo "1. Locate the RPI-RP2 drive that appears"
            echo "2. Copy the firmware file to it:"
            echo "   cp $FIRMWARE_FILE /path/to/RPI-RP2/"
            exit 1
        fi
        PICO_PATH=$(detect_pico)
    fi
fi

# Verify it's a Pico
if [ ! -f "$PICO_PATH/INFO_UF2.TXT" ]; then
    echo -e "${RED}Error: This doesn't appear to be a Pico in bootloader mode${NC}"
    echo "INFO_UF2.TXT not found in $PICO_PATH"
    exit 1
fi

# Show Pico info
echo ""
echo -e "${BLUE}Pico Information:${NC}"
cat "$PICO_PATH/INFO_UF2.TXT" | head -2
echo ""

# Copy firmware
echo -e "${YELLOW}Flashing firmware...${NC}"
cp -v "$FIRMWARE_FILE" "$PICO_PATH/"

# Wait for device to unmount (indicates successful flash)
echo -e "${YELLOW}Waiting for Pico to reboot...${NC}"
sleep 2

if [ -d "$PICO_PATH" ]; then
    # Still mounted, might need sync
    sync
    sleep 1
fi

if [ ! -d "$PICO_PATH" ]; then
    echo -e "${GREEN}==================================${NC}"
    echo -e "${GREEN}  Flash Successful!${NC}"
    echo -e "${GREEN}==================================${NC}"
    echo ""
    echo "The Pico has rebooted with the new firmware."
    echo "You can now connect via Bluetooth with your gamepad."
else
    echo -e "${YELLOW}Warning: Pico may still be mounted${NC}"
    echo "The firmware has been copied, but you may need to:"
    echo "1. Safely eject the RPI-RP2 drive"
    echo "2. Or unplug and reconnect the Pico"
fi