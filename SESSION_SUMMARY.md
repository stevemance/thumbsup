# Session Summary - DShot Debug & AM32 Config Reader

## Date
2026-01-09

## Objectives
1. Read AM32 ESC configuration to verify settings
2. Debug DShot implementation - motor not spinning

## Major Accomplishments

### 1. Successfully Implemented AM32 Bootloader Protocol Reader

**File:** `/home/smance/projects/thumbsup/firmware/src/phase6_am32_config.c`

Successfully read ESC configuration via bootloader protocol:
- **Protocol:** AM32 bootloader (19200 baud, CRC-16 polynomial 0xA001)
- **Method:** Bit-banged half-duplex UART on GP4
- **EEPROM Address:** 0x7C00 (discovered from AM32 source: `EEPROM_START_ADD = 0x08007C00`)

**ESC Configuration Retrieved:**
```
EEPROM Version:           3
Firmware Version:         2.19
Motor KV:                 27
Motor Poles:              14
Direction Reversed:       0 (Normal)
Bidirectional/3D Mode:    0 (OFF) ✓
Brake on Stop:            1 (Enabled)
PWM Frequency:            24 kHz
Advance Level:            16
Auto Advance:             1 (Enabled)
Startup Power:            100
Current Limit:            5
Temperature Limit:        70°C
Stuck Rotor Protection:   0 (Disabled)
Stall Protection:         0 (Disabled)
Telemetry Interval:       0 (Disabled initially, user enabled later)
```

**Key Finding:** Confirmed 3D mode is OFF - ESC configuration is correct.

### 2. Critical DShot Bug Fixed

**Problem:** Motor not spinning with DShot commands despite correct ESC configuration.

**Root Cause:** CRC algorithm was completely wrong.

**Analysis:** Spawned task agent to compare our DShot implementation with AM32's actual source code.

**Discovery:** DShot CRC is a simple XOR of three 4-bit nibbles, NOT a polynomial CRC.

**Fix Applied:**
```c
// BEFORE (WRONG - polynomial CRC):
uint8_t dshot_calculate_crc(uint16_t packet) {
    uint16_t crc = 0;
    uint16_t data = packet;
    for (int i = 0; i < 12; i++) {
        crc ^= (data & 0x800) ? 0x8 : 0;
        data <<= 1;
        crc <<= 1;
        if (crc & 0x10) {
            crc ^= 0x19;
        }
    }
    return crc & 0x0F;
}

// AFTER (CORRECT - XOR of nibbles):
uint8_t dshot_calculate_crc(uint16_t packet) {
    // DShot CRC is XOR of three 4-bit nibbles
    // This matches AM32's CRC verification algorithm
    return ((packet ^ (packet >> 4) ^ (packet >> 8)) & 0x0F);
}
```

**File Modified:** `/home/smance/projects/thumbsup/firmware/src/dshot.c`

**Status:** Fix applied, rebuilt, and loaded. Test was running when session ended.

## Technical Details

### AM32 Bootloader Protocol
- **Baud Rate:** 19200, 8N1
- **CRC:** CRC-16 with polynomial 0xA001 (CRC-16-IBM/ANSI)
- **Bootloader Entry:** Hold signal HIGH during ESC power cycle
- **Commands Used:**
  - `CMD_SET_ADDRESS = 0xFF` - Set flash read address
  - `CMD_READ_FLASH_SIL = 0x03` - Read flash memory
  - `ACK_OK = 0x30` - Command acknowledged
- **EEPROM Location:** 0x7C00 (from `targets.h` line 4920)

### DShot Protocol Details (from AM32 source)
- **Packet Structure:** [11-bit throttle][1-bit telemetry][4-bit CRC]
- **CRC Algorithm:** `(packet ^ (packet >> 4) ^ (packet >> 8)) & 0x0F`
- **Throttle Range:** 0-47 reserved for commands, 48-2047 valid throttle
- **Timing (DShot300):** 3.33μs per bit
  - Logic 0: ~37.5% HIGH, ~62.5% LOW
  - Logic 1: ~62.5% HIGH, ~37.5% LOW
- **Update Rate:** ESCs expect continuous updates every 1-2ms

## Files Modified This Session

1. `/home/smance/projects/thumbsup/firmware/src/phase6_am32_config.c` - Created AM32 config reader
2. `/home/smance/projects/thumbsup/firmware/src/dshot.c` - Fixed CRC algorithm
3. `/home/smance/projects/thumbsup/firmware/CMakeLists.txt` - Added phase6_am32_config build target

## Test Firmwares Built

1. `phase6_am32_config.uf2` - Reads and displays ESC configuration
2. `phase3_motor_spin.uf2` - Motor spin test (with CRC fix)
3. `phase4_telemetry_test.uf2` - Telemetry test (no packets received yet)

## Current Status

**Motor Spin:** NOT YET VERIFIED
- CRC fix applied and firmware loaded
- Test was interrupted by user before completion
- Need to verify motor spins on next session

**Next Steps:**
1. Verify motor spins with corrected DShot CRC
2. If still not spinning, check other potential issues from analysis:
   - Inverted CRC for bidirectional mode
   - EDT arming sequence (may need command 13 first)
   - PIO timing verification with oscilloscope
3. Enable and test telemetry reception

## Resources Used

- **AM32 Firmware Repository:** Cloned to `/tmp/am32_firmware`
- **Key Files Analyzed:**
  - `/tmp/am32_firmware/Src/dshot.c` - ESC-side DShot implementation
  - `/tmp/am32_firmware/Inc/targets.h` - MCU configurations and EEPROM addresses
  - `/tmp/am32_firmware/Inc/eeprom.h` - EEPROM structure definition
  - `/tmp/am32_firmware/Mcu/f421/Src/eeprom.c` - AT32F421 flash operations

## Hardware Configuration

- **MCU:** Raspberry Pi Pico W (RP2040)
- **ESC:** AT32F421-based AM32 ESC (firmware v2.19)
- **Motor:** FingerTech Silver Spark F2822-1100KV (14 poles)
- **Protocol:** DShot300
- **Signal Pin:** GP4 (motor 2)
- **Test Environment:** USB serial @ 115200 baud

## Git Status Before Commit

Modified files:
- `firmware/CMakeLists.txt`
- `firmware/src/bluetooth_platform.c`
- `firmware/src/dshot.c`
- `firmware/src/dshot.pio`
- `firmware/src/weapon.c`

Untracked files:
- `CLAUDE.md`
- `firmware/src/esc_test.c`
- `firmware/src/phase2_dshot_verify.c`
- `firmware/src/phase3_motor_spin.c`
- `firmware/src/phase4_telemetry_test.c`
- `firmware/src/phase5_pwm_test.c`
- `firmware/src/phase6_am32_config.c`
