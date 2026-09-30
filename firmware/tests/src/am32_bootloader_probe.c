#include <stdio.h>
#include <pico/stdlib.h>
#include "pico/stdio_usb.h"
#include "am32_bootloader.h"

static void wait_for_usb(void) {
    for (int i = 0; i < 100; i++) {
        if (stdio_usb_connected()) {
            break;
        }
        sleep_ms(50);
    }
}

static void print_device_info(const uint8_t devinfo[AM32_DEVICE_INFO_SIZE]) {
    printf("Bootloader device info:\n");
    printf("  Signature: %c%c%c\n", devinfo[0], devinfo[1], devinfo[2]);
    printf("  Pin code:  0x%02X\n", devinfo[3]);
    printf("  Flash:     0x%02X\n", devinfo[4]);
    printf("  Proto ver: %u\n", devinfo[7]);
    printf("  ACK byte:  0x%02X\n", devinfo[8]);
}

static void dump_raw_prefix(const uint8_t* data, size_t len) {
    size_t n = len < 64 ? len : 64;
    printf("Raw EEPROM [0..%zu):\n", n);
    for (size_t i = 0; i < n; i++) {
        printf("%02X ", data[i]);
        if ((i + 1) % 16 == 0) {
            printf("\n");
        }
    }
    if (n % 16 != 0) {
        printf("\n");
    }
}

static bool looks_like_code(const uint8_t* data, size_t len) {
    if (!data || len < 32) {
        return false;
    }
    size_t words = len / 4;
    size_t ptr_like = 0;
    for (size_t i = 0; i < words; i++) {
        const size_t o = i * 4;
        if (data[o + 3] == 0x08 && data[o + 2] == 0x00) {
            ptr_like++;
        }
    }
    return ptr_like >= 4;
}

static void scan_candidate_eeprom_offsets(void) {
    printf("\nScanning candidate EEPROM offsets...\n");
    for (uint16_t addr = 0x7000; addr <= 0x7F00; addr += 0x100) {
        uint8_t tmp[32] = {0};
        am32_bootloader_error_t err = am32_bootloader_read_at(addr, tmp, sizeof(tmp));
        if (err != AM32_OK) {
            printf("  0x%04X: read failed (%s)\n", addr, am32_bootloader_error_str(err));
            continue;
        }
        bool code_like = looks_like_code(tmp, sizeof(tmp));
        printf("  0x%04X: %s  first16=", addr, code_like ? "code-like" : "data-like");
        for (int i = 0; i < 16; i++) {
            printf("%02X ", tmp[i]);
        }
        printf("\n");
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);
    wait_for_usb();

    printf("\n========================================\n");
    printf("  AM32 Bootloader Probe (Read-Only)\n");
    printf("========================================\n\n");
    printf("This uses the AM32 bootloader protocol over GP4.\n");
    printf("Power-cycle the ESC while the signal line is held HIGH.\n");
    printf("The probe will retry reads until it succeeds.\n\n");

    am32_bootloader_init();
    am32_bootloader_hold_high();
    printf("Signal line held HIGH. You can power-cycle the ESC now.\n\n");

    uint8_t cfg[AM32_EEPROM_SIZE] = {0};
    uint32_t attempt = 0;
    while (true) {
        attempt++;
        printf("Probe attempt %lu...\n", attempt);
        am32_bootloader_hold_high();

        am32_bootloader_error_t err = am32_bootloader_enter();
        if (err != AM32_OK) {
            printf("Bootloader entry failed: %s\n", am32_bootloader_error_str(err));
            sleep_ms(1000);
            continue;
        }
        uint32_t baud = am32_bootloader_get_last_baud();
        if (baud > 0) {
            printf("Bootloader handshake baud: %lu\n", baud);
        }

        uint8_t devinfo[AM32_DEVICE_INFO_SIZE] = {0};
        if (am32_bootloader_get_device_info(devinfo)) {
            print_device_info(devinfo);
        } else {
            printf("Bootloader device info not captured (continuing)\n");
        }

        char file_name[64] = {0};
        err = am32_bootloader_read_filename(file_name, sizeof(file_name));
        if (err == AM32_OK) {
            printf("Firmware FILE_NAME: %s\n", file_name);
        } else {
            printf("FILE_NAME read failed: %s\n", am32_bootloader_error_str(err));
        }

        err = am32_bootloader_read(cfg);
        if (err == AM32_OK) {
            printf("EEPROM read OK.\n");
            dump_raw_prefix(cfg, AM32_EEPROM_SIZE);
            if (looks_like_code(cfg, AM32_EEPROM_SIZE)) {
                printf("WARN: read block looks like code, not config EEPROM.\n");
                scan_candidate_eeprom_offsets();
            }
            am32_bootloader_print(cfg);
            break;
        }

        printf("EEPROM read failed: %s\n", am32_bootloader_error_str(err));
        sleep_ms(1000);
    }

    printf("\nRead complete. Leaving ESC in bootloader mode.\n");
    while (1) {
        sleep_ms(1000);
    }
}
