// Simple WiFi AP test for Pico W
#include <stdio.h>
#include <pico/stdlib.h>
#include <pico/cyw43_arch.h>
#include <hardware/watchdog.h>

#define WIFI_SSID "ThumbsUp_Test"
#define WIFI_PASSWORD "combat123"

int main() {
    // Initialize stdio for USB serial debugging
    stdio_init_all();

    // Wait a bit for USB serial to connect
    for (int i = 0; i < 5; i++) {
        printf("Starting in %d...\n", 5-i);
        sleep_ms(1000);
    }

    printf("\n=================================\n");
    printf("  WiFi AP Test Program\n");
    printf("=================================\n\n");

    // Initialize CYW43 driver for WiFi
    printf("Initializing CYW43...\n");
    if (cyw43_arch_init_with_country(CYW43_COUNTRY_USA)) {
        printf("ERROR: Failed to initialize CYW43!\n");
        while (1) {
            sleep_ms(1000);
        }
    }
    printf("CYW43 initialized successfully\n");

    // Turn on LED to show we're running
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);

    // Enable AP mode
    printf("Starting WiFi AP...\n");
    printf("  SSID: %s\n", WIFI_SSID);
    printf("  Password: %s\n", WIFI_PASSWORD);

    cyw43_arch_enable_ap_mode(WIFI_SSID, WIFI_PASSWORD, CYW43_AUTH_WPA2_AES_PSK);

    printf("WiFi AP should be running!\n");
    printf("\nWiFi AP is ready!\n");
    printf("Connect to SSID: %s\n", WIFI_SSID);
    printf("Password: %s\n", WIFI_PASSWORD);

    // Blink LED to show we're alive
    uint32_t last_time = 0;
    bool led_state = true;

    while (true) {
        // Poll WiFi driver
        cyw43_arch_poll();

        // Blink LED every second
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now - last_time > 1000) {
            last_time = now;
            led_state = !led_state;
            cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, led_state);
            printf("Heartbeat... (uptime: %lu seconds)\n", now / 1000);
        }

        sleep_ms(10);
    }

    return 0;
}