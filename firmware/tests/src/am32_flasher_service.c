#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pico/stdio_usb.h"
#include "pico/stdlib.h"

#include "am32_bootloader.h"

#define LINE_MAX 800
#define HEXCFG_LEN (AM32_EEPROM_SIZE * 2)

static bool bl_ready = false;

static void strip_line(char* s) {
    if (!s) {
        return;
    }
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[--n] = '\0';
    }
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return 10 + (c - 'a');
    }
    if (c >= 'A' && c <= 'F') {
        return 10 + (c - 'A');
    }
    return -1;
}

static bool parse_hex_u16(const char* s, uint16_t* out) {
    if (!s || !out) {
        return false;
    }
    char* end = NULL;
    unsigned long v = strtoul(s, &end, 16);
    if (end == s || *end != '\0' || v > 0xFFFFu) {
        return false;
    }
    *out = (uint16_t)v;
    return true;
}

static bool parse_len_u16(const char* s, uint16_t* out) {
    if (!s || !out) {
        return false;
    }
    char* end = NULL;
    unsigned long v = strtoul(s, &end, 0);
    if (end == s || *end != '\0' || v > 0xFFFFu) {
        return false;
    }
    *out = (uint16_t)v;
    return true;
}

static bool parse_hex_bytes(const char* hex, uint8_t* out, uint16_t cap, uint16_t* out_len) {
    if (!hex || !out || !out_len) {
        return false;
    }
    size_t n = strlen(hex);
    if ((n % 2) != 0) {
        return false;
    }
    uint16_t len = (uint16_t)(n / 2);
    if (len > cap) {
        return false;
    }
    for (uint16_t i = 0; i < len; i++) {
        int hi = hex_nibble(hex[2u * i]);
        int lo = hex_nibble(hex[2u * i + 1u]);
        if (hi < 0 || lo < 0) {
            return false;
        }
        out[i] = (uint8_t)((hi << 4) | lo);
    }
    *out_len = len;
    return true;
}

static void print_hex(const uint8_t* data, uint16_t len) {
    for (uint16_t i = 0; i < len; i++) {
        printf("%02X", data[i]);
    }
}

static bool ensure_bootloader(void) {
    if (bl_ready) {
        return true;
    }
    am32_bootloader_init();
    am32_bootloader_error_t err = am32_bootloader_enter();
    if (err != AM32_OK) {
        printf("ERR ENTER %s\n", am32_bootloader_error_str(err));
        return false;
    }
    bl_ready = true;
    return true;
}

static void handle_info(void) {
    if (!ensure_bootloader()) {
        return;
    }
    uint8_t dev[AM32_DEVICE_INFO_SIZE] = {0};
    char name[64] = {0};
    bool have_dev = am32_bootloader_get_device_info(dev);
    am32_bootloader_error_t nerr = am32_bootloader_read_filename(name, sizeof(name));
    if (!have_dev) {
        printf("ERR INFO no_device_info\n");
        return;
    }
    if (nerr != AM32_OK) {
        printf("ERR INFO filename_%s\n", am32_bootloader_error_str(nerr));
        return;
    }
    printf("OK INFO sig=%c%c%c pin=0x%02X flash=0x%02X proto=%u ack=0x%02X name=%s\n",
           dev[0], dev[1], dev[2], dev[3], dev[4], dev[7], dev[8], name);
}

static void handle_read_cfg(void) {
    if (!ensure_bootloader()) {
        return;
    }
    uint8_t cfg[AM32_EEPROM_SIZE] = {0};
    am32_bootloader_error_t err = am32_bootloader_read(cfg);
    if (err != AM32_OK) {
        printf("ERR READCFG %s\n", am32_bootloader_error_str(err));
        return;
    }
    printf("DATA CFG ");
    print_hex(cfg, AM32_EEPROM_SIZE);
    printf("\n");
}

static void handle_write_cfg(const char* hex) {
    if (!hex) {
        printf("ERR WRITECFG missing_hex\n");
        return;
    }
    if (strlen(hex) != HEXCFG_LEN) {
        printf("ERR WRITECFG expected_%u_hex_chars\n", (unsigned)HEXCFG_LEN);
        return;
    }
    if (!ensure_bootloader()) {
        return;
    }
    uint8_t cfg[AM32_EEPROM_SIZE] = {0};
    uint16_t len = 0;
    if (!parse_hex_bytes(hex, cfg, sizeof(cfg), &len) || len != AM32_EEPROM_SIZE) {
        printf("ERR WRITECFG invalid_hex\n");
        return;
    }
    am32_bootloader_error_t err = am32_bootloader_write(cfg);
    if (err != AM32_OK) {
        printf("ERR WRITECFG %s\n", am32_bootloader_error_str(err));
        return;
    }
    uint8_t verify[AM32_EEPROM_SIZE] = {0};
    err = am32_bootloader_read(verify);
    if (err != AM32_OK) {
        printf("ERR WRITECFG_VERIFY %s\n", am32_bootloader_error_str(err));
        return;
    }
    if (memcmp(cfg, verify, AM32_EEPROM_SIZE) != 0) {
        printf("ERR WRITECFG_VERIFY mismatch\n");
        return;
    }
    printf("OK WRITECFG\n");
}

static void handle_read_at(const char* addr_s, const char* len_s) {
    if (!addr_s || !len_s) {
        printf("ERR READAT usage_READAT_addr_hex_len\n");
        return;
    }
    if (!ensure_bootloader()) {
        return;
    }
    uint16_t addr = 0;
    uint16_t len = 0;
    if (!parse_hex_u16(addr_s, &addr) || !parse_len_u16(len_s, &len) || len == 0 || len > 256) {
        printf("ERR READAT bad_args\n");
        return;
    }
    uint8_t buf[256] = {0};
    am32_bootloader_error_t err = am32_bootloader_read_at(addr, buf, len);
    if (err != AM32_OK) {
        printf("ERR READAT %s\n", am32_bootloader_error_str(err));
        return;
    }
    printf("DATA READAT addr=0x%04X len=%u ", addr, len);
    print_hex(buf, len);
    printf("\n");
}

static void handle_flash(const char* addr_s, const char* hex) {
    if (!addr_s || !hex) {
        printf("ERR FLASH usage_FLASH_addr_hex_data_hex\n");
        return;
    }
    if (!ensure_bootloader()) {
        return;
    }
    uint16_t addr = 0;
    if (!parse_hex_u16(addr_s, &addr)) {
        printf("ERR FLASH bad_addr\n");
        return;
    }
    uint8_t payload[256] = {0};
    uint16_t len = 0;
    if (!parse_hex_bytes(hex, payload, sizeof(payload), &len) || len == 0) {
        printf("ERR FLASH bad_data\n");
        return;
    }
    am32_bootloader_error_t err = am32_bootloader_program_flash(addr, payload, len);
    if (err != AM32_OK) {
        printf("ERR FLASH %s\n", am32_bootloader_error_str(err));
        return;
    }
    printf("OK FLASH addr=0x%04X len=%u\n", addr, len);
}

static void handle_run(void) {
    if (!ensure_bootloader()) {
        return;
    }
    am32_bootloader_run();
    bl_ready = false;
    printf("OK RUN\n");
}

static void print_help(void) {
    printf("OK HELP commands=PING,HELP,ENTER,INFO,READCFG,WRITECFG,READAT,FLASH,RUN\n");
    printf("OK HELP WRITECFG hex_chars=%u\n", (unsigned)HEXCFG_LEN);
}

static void process_command(char* line) {
    strip_line(line);
    if (line[0] == '\0') {
        return;
    }

    char* saveptr = NULL;
    char* cmd = strtok_r(line, " \t", &saveptr);
    if (!cmd) {
        return;
    }
    for (char* p = cmd; *p; p++) {
        *p = (char)toupper((unsigned char)*p);
    }

    if (strcmp(cmd, "PING") == 0) {
        printf("OK PONG\n");
    } else if (strcmp(cmd, "HELP") == 0) {
        print_help();
    } else if (strcmp(cmd, "ENTER") == 0) {
        if (ensure_bootloader()) {
            printf("OK ENTER baud=%lu\n", am32_bootloader_get_last_baud());
        }
    } else if (strcmp(cmd, "INFO") == 0) {
        handle_info();
    } else if (strcmp(cmd, "READCFG") == 0) {
        handle_read_cfg();
    } else if (strcmp(cmd, "WRITECFG") == 0) {
        char* hex = strtok_r(NULL, " \t", &saveptr);
        handle_write_cfg(hex);
    } else if (strcmp(cmd, "READAT") == 0) {
        char* addr_s = strtok_r(NULL, " \t", &saveptr);
        char* len_s = strtok_r(NULL, " \t", &saveptr);
        handle_read_at(addr_s, len_s);
    } else if (strcmp(cmd, "FLASH") == 0) {
        char* addr_s = strtok_r(NULL, " \t", &saveptr);
        char* hex = strtok_r(NULL, " \t", &saveptr);
        handle_flash(addr_s, hex);
    } else if (strcmp(cmd, "RUN") == 0) {
        handle_run();
    } else {
        printf("ERR unknown_command\n");
    }
}

int main(void) {
    stdio_init_all();
    sleep_ms(1500);

    for (int i = 0; i < 120; i++) {
        if (stdio_usb_connected()) {
            break;
        }
        sleep_ms(25);
    }

    printf("OK AM32_FLASHER_SERVICE ready\n");
    print_help();

    char line[LINE_MAX];
    size_t n = 0;

    while (true) {
        int ch = getchar_timeout_us(100000);
        if (ch < 0) {
            tight_loop_contents();
            continue;
        }
        if (ch == '\r' || ch == '\n') {
            if (n > 0) {
                line[n] = '\0';
                process_command(line);
                n = 0;
            }
            continue;
        }
        if (n + 1 < sizeof(line)) {
            line[n++] = (char)ch;
        } else {
            // Reset on overflow to preserve parser integrity.
            n = 0;
            printf("ERR line_too_long\n");
        }
    }
}
