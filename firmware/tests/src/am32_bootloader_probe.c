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
        printf("Holding HIGH for power cycle (attempt %lu)...\n", attempt);
        am32_bootloader_hold_high();
        sleep_ms(3000);
        printf("EEPROM read attempt %lu...\n", attempt);
        am32_bootloader_error_t err = am32_bootloader_read(cfg);
        if (err == AM32_OK) {
            printf("EEPROM read OK.\n");
            am32_bootloader_print(cfg);
            break;
        }

        printf("EEPROM read failed: %s\n", am32_bootloader_error_str(err));
        am32_bootloader_hold_high();
        sleep_ms(1000);
    }

    printf("\nRead complete. Leaving ESC in bootloader mode.\n");
    while (1) {
        sleep_ms(1000);
    }
}
