#include "trim_mode.h"
#include "status.h"
#include "config.h"
#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include <uni.h>
#include <stdio.h>
#include <string.h>

// Flash storage configuration
// Store trim data in the last sector of flash (2MB - 4KB for Pico W)
#define FLASH_TARGET_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)
#define TRIM_MAGIC 0x54524D31  // "TRM1" magic number for validation

// Trim data structure stored in flash
typedef struct {
    uint32_t magic;
    int8_t trim_30_percent;  // Trim at 30% power
    int8_t trim_70_percent;  // Trim at 70% power
    uint8_t reserved[2];     // Padding for alignment
    uint32_t checksum;       // Simple checksum for validation
} __attribute__((packed)) trim_data_t;

// Trim mode state
static trim_mode_state_t trim_state = TRIM_MODE_INACTIVE;
static trim_level_t current_level = TRIM_LEVEL_30_PERCENT;
static int8_t trim_30 = 0;  // Saved trim at 30% power
static int8_t trim_70 = 0;  // Saved trim at 70% power
static int8_t working_trim = 0; // Trim being adjusted during current calibration level

// Activation tracking
static bool activation_buttons_held = false;
static uint32_t activation_hold_start = 0;
#define ACTIVATION_HOLD_TIME_MS 2000  // 2 seconds to enter/exit

// Level switching
static bool level_button_prev = false;
#define LEVEL_BUTTON_MASK BTN_Y  // Y button to advance levels

// Calculate simple checksum
static uint32_t calculate_checksum(const trim_data_t *data) {
    return data->magic + data->trim_30_percent + data->trim_70_percent;
}

// Get flash memory pointer
static const trim_data_t* get_flash_trim_data(void) {
    return (const trim_data_t*)(XIP_BASE + FLASH_TARGET_OFFSET);
}

bool trim_mode_init(void) {
    trim_state = TRIM_MODE_INACTIVE;
    current_level = TRIM_LEVEL_30_PERCENT;
    trim_30 = 0;
    trim_70 = 0;
    working_trim = 0;

    // Try to load saved trim from flash
    if (trim_mode_load()) {
        printf("Trim mode: Loaded trim 30%%=%d, 70%%=%d\n", trim_30, trim_70);
    } else {
        printf("Trim mode: No valid trim data found, using defaults (0, 0)\n");
        trim_30 = 0;
        trim_70 = 0;
    }

    return true;
}

bool trim_mode_load(void) {
    const trim_data_t *flash_data = get_flash_trim_data();

    // Validate magic number
    if (flash_data->magic != TRIM_MAGIC) {
        return false;
    }

    // Validate checksum
    if (flash_data->checksum != calculate_checksum(flash_data)) {
        return false;
    }

    // Validate trim ranges
    if (flash_data->trim_30_percent < -100 || flash_data->trim_30_percent > 100) {
        return false;
    }
    if (flash_data->trim_70_percent < -100 || flash_data->trim_70_percent > 100) {
        return false;
    }

    // Load the trim values
    trim_30 = flash_data->trim_30_percent;
    trim_70 = flash_data->trim_70_percent;
    return true;
}

bool trim_mode_save(void) {
    trim_data_t data = {
        .magic = TRIM_MAGIC,
        .trim_30_percent = trim_30,
        .trim_70_percent = trim_70,
        .reserved = {0, 0},
        .checksum = 0
    };

    // Calculate checksum
    data.checksum = calculate_checksum(&data);

    // Prepare buffer (must be 256-byte aligned for flash write)
    uint8_t buffer[FLASH_PAGE_SIZE];
    memset(buffer, 0xFF, FLASH_PAGE_SIZE);
    memcpy(buffer, &data, sizeof(trim_data_t));

    // Disable interrupts during flash operation
    uint32_t ints = save_and_disable_interrupts();

    // Erase the sector
    flash_range_erase(FLASH_TARGET_OFFSET, FLASH_SECTOR_SIZE);

    // Write the page
    flash_range_program(FLASH_TARGET_OFFSET, buffer, FLASH_PAGE_SIZE);

    // Re-enable interrupts
    restore_interrupts(ints);

    printf("Trim mode: Saved trim 30%%=%d, 70%%=%d to flash\n", trim_30, trim_70);
    return true;
}

void trim_mode_check_activation(trim_gamepad_ptr gp_ptr) {
    uni_gamepad_t *gp = (uni_gamepad_t*)gp_ptr;
    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // Check if both joystick buttons (L3 + R3) are pressed
    bool both_sticks = (gp->buttons & BTN_L3) && (gp->buttons & BTN_R3);

    if (both_sticks) {
        if (!activation_buttons_held) {
            // Just started holding
            activation_buttons_held = true;
            activation_hold_start = current_time;
            printf("Trim mode: Hold L3+R3 for 2s to %s...\n",
                   trim_state == TRIM_MODE_INACTIVE ? "enter" : "exit");
        } else if (current_time - activation_hold_start >= ACTIVATION_HOLD_TIME_MS) {
            // Held long enough - toggle trim mode
            if (trim_state == TRIM_MODE_INACTIVE) {
                // Enter trim mode
                trim_state = TRIM_MODE_ACTIVE;
                current_level = TRIM_LEVEL_30_PERCENT;
                working_trim = trim_30;  // Start with current 30% trim

                printf("\n=== MOTOR TRIM CALIBRATION MODE ===\n");
                printf("Level 1: 30%% power\n");
                printf("- Robot will drive forward at 30%% speed\n");
                printf("- Use left stick X-axis to steer until straight\n");
                printf("- Press Y button to advance to 70%% power\n");
                printf("- Hold L3+R3 for 2s to save and exit\n");
                printf("Current trim: 30%%=%d, 70%%=%d\n\n", trim_30, trim_70);

                // Set LED to show trim mode
                status_set_system(SYSTEM_STATUS_READY, LED_EFFECT_BLINK_MEDIUM);
                status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

            } else {
                // Exit trim mode - save both trim values
                trim_state = TRIM_MODE_INACTIVE;

                // Save the working trim to the appropriate level
                if (current_level == TRIM_LEVEL_30_PERCENT) {
                    trim_30 = working_trim;
                } else {
                    trim_70 = working_trim;
                }

                printf("\n=== EXITING TRIM MODE ===\n");
                printf("Saving trim values: 30%%=%d, 70%%=%d\n", trim_30, trim_70);

                trim_mode_save();

                printf("Trim mode saved. Returning to normal operation.\n\n");

                // Restore normal LED status
                status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
            }

            // Reset to prevent immediate re-trigger
            activation_buttons_held = false;
            activation_hold_start = 0;
        }
    } else {
        // Buttons released - reset
        activation_buttons_held = false;
        activation_hold_start = 0;
    }
}

bool trim_mode_update(trim_gamepad_ptr gp_ptr) {
    if (trim_state == TRIM_MODE_INACTIVE) {
        return false;
    }

    uni_gamepad_t *gp = (uni_gamepad_t*)gp_ptr;

    // Check for level advancement (Y button press)
    bool level_button = (gp->buttons & LEVEL_BUTTON_MASK) != 0;
    if (level_button && !level_button_prev) {
        // Button just pressed - save current working trim and switch levels
        if (current_level == TRIM_LEVEL_30_PERCENT) {
            trim_30 = working_trim;  // Save 30% trim
            current_level = TRIM_LEVEL_70_PERCENT;
            working_trim = trim_70;   // Load 70% trim
            printf("\n=== Trim Level 2: 70%% power ===\n");
            printf("30%% trim saved as: %d\n", trim_30);
            printf("Continue adjusting until robot drives straight at 70%% power\n");
            printf("Hold L3+R3 for 2s to save and exit\n\n");
        } else {
            trim_70 = working_trim;  // Save 70% trim
            current_level = TRIM_LEVEL_30_PERCENT;
            working_trim = trim_30;   // Load 30% trim
            printf("\n=== Back to Level 1: 30%% power ===\n");
            printf("70%% trim saved as: %d\n\n", trim_70);
        }
    }
    level_button_prev = level_button;

    // Read steering input from left stick X-axis
    int32_t raw_turn = gp->axis_x;
    raw_turn = CLAMP(raw_turn, -512, 511);

    // Apply deadzone
    int32_t turn = 0;
    if (abs(raw_turn) > STICK_DEADZONE) {
        if (raw_turn > 0) {
            turn = ((raw_turn - STICK_DEADZONE) * 511) / (511 - STICK_DEADZONE);
        } else {
            turn = ((raw_turn + STICK_DEADZONE) * 512) / (512 - STICK_DEADZONE);
        }
    }

    // Convert to -100 to +100 range and update working trim
    // This is the offset needed to make the robot go straight
    working_trim = (int8_t)((turn * 100) / 512);
    working_trim = CLAMP(working_trim, -100, 100);

    // Debugging output (throttled)
    static uint32_t last_print = 0;
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if (now - last_print > 500) {
        printf("Trim: %d  Turn input: %d  Level: %s\n",
               working_trim, turn,
               current_level == TRIM_LEVEL_30_PERCENT ? "30%" : "70%");
        last_print = now;
    }

    return true;  // Trim mode is active
}

bool trim_mode_is_active(void) {
    return trim_state == TRIM_MODE_ACTIVE;
}

int8_t trim_mode_get_offset(uint8_t drive_power_percent) {
    // If in trim mode, return the working trim (what's being adjusted)
    if (trim_state == TRIM_MODE_ACTIVE) {
        return working_trim;
    }

    // Normal operation: interpolate between 30% and 70% calibration points
    // This handles motor non-linearity across the power range

    // Clamp drive power to valid range
    if (drive_power_percent > 100) {
        drive_power_percent = 100;
    }

    // Below 30%: use 30% trim
    if (drive_power_percent <= 30) {
        return trim_30;
    }

    // Above 70%: use 70% trim
    if (drive_power_percent >= 70) {
        return trim_70;
    }

    // Between 30% and 70%: linear interpolation
    // interpolation_factor = 0.0 at 30%, 1.0 at 70%
    float interpolation_factor = (float)(drive_power_percent - 30) / 40.0f;

    // Interpolate between the two trim values
    float interpolated = trim_30 + (trim_70 - trim_30) * interpolation_factor;

    return (int8_t)(interpolated + 0.5f);  // Round to nearest integer
}

trim_level_t trim_mode_get_level(void) {
    return current_level;
}

void trim_mode_reset(void) {
    trim_30 = 0;
    trim_70 = 0;
    working_trim = 0;
    trim_mode_save();
    printf("Trim reset to 30%%=0, 70%%=0\n");
}
