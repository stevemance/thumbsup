#include "trim_mode.h"
#include "status.h"
#include "config.h"
#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

// Only include uni.h in competition mode (when Bluepad32 is available)
#if !DIAGNOSTIC_MODE_BUILD
#include <uni.h>
#endif

// Flash storage configuration
// Store trim data in the last sector of flash (2MB - 4KB for Pico W)
#define FLASH_TARGET_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)
#define TRIM_MAGIC_V2 0x54524D32  // "TRM2" magic number for new version

// Minimum samples required to save
#define MIN_SAMPLES_TO_SAVE 5

// Minimum speed threshold - samples below this are discarded
#define MIN_SPEED_THRESHOLD 5

// Maximum samples per direction after downsampling
#define MAX_SAMPLES_PER_DIRECTION 20

// Outlier rejection threshold (standard deviations)
#define OUTLIER_THRESHOLD 3.0f

// LED feedback duration in milliseconds
#define LED_FEEDBACK_BLINK_MS 200
#define LED_FEEDBACK_SOLID_MS 1000

// Trim data structure stored in flash
typedef struct {
    uint32_t magic;                       // Magic number for validation
    uint8_t num_samples;                  // Number of valid samples
    trim_sample_t samples[MAX_TRIM_SAMPLES]; // Sample array
    uint8_t reserved[3];                  // Padding for alignment
    uint32_t checksum;                    // Simple checksum
} __attribute__((packed)) trim_data_flash_t;

// Runtime state
static trim_mode_state_t trim_state = TRIM_MODE_INACTIVE;
static trim_sample_t samples[MAX_TRIM_SAMPLES];
static uint8_t num_samples = 0;
static trim_sample_t fitted_samples[MAX_TRIM_SAMPLES]; // Cleaned and sorted samples
static uint8_t num_fitted_samples = 0;

// Activation tracking
static bool activation_buttons_held = false;
static uint32_t activation_hold_start = 0;
#define ACTIVATION_HOLD_TIME_MS 2000  // 2 seconds to enter/exit

// Button state tracking for edge detection
static bool button_a_prev = false;
static bool button_b_prev = false;

// Feedback state for non-blocking LED flashes
typedef enum {
    FEEDBACK_NONE,
    FEEDBACK_CAPTURED,
    FEEDBACK_REMOVED,
    FEEDBACK_EXIT_SUCCESS,
    FEEDBACK_EXIT_ERROR
} feedback_state_t;

static feedback_state_t feedback_state = FEEDBACK_NONE;
static uint32_t feedback_start_time = 0;
#define FEEDBACK_FLASH_DURATION_MS 750  // Long enough to see clearly
#define FEEDBACK_EXIT_DURATION_MS 1500  // Show exit feedback longer

// Bright colors for feedback (full brightness) - use GRB format (0x00GGRRBB)
#define FEEDBACK_COLOR_CAPTURED  0x00FF0000  // Bright GREEN in GRB for adding (A button)
#define FEEDBACK_COLOR_REMOVED   0x0000FF00  // Bright RED in GRB for removing (B button)

// LED feedback functions - non-blocking, just change the LED state
static void trim_feedback_captured(void) {
    // Bright green flash
    feedback_state = FEEDBACK_CAPTURED;
    feedback_start_time = to_ms_since_boot(get_absolute_time());
    status_set_led_color(0, FEEDBACK_COLOR_CAPTURED, LED_EFFECT_SOLID);
    printf("Trim: Sample captured! (%d total)\n", num_samples);
}

static void trim_feedback_removed(void) {
    // Bright red flash
    feedback_state = FEEDBACK_REMOVED;
    feedback_start_time = to_ms_since_boot(get_absolute_time());
    status_set_led_color(0, FEEDBACK_COLOR_REMOVED, LED_EFFECT_SOLID);
    printf("Trim: Sample removed! (%d remaining)\n", num_samples);
}

static void trim_feedback_fitting(void) {
    // Orange pulsing while fitting curves
    status_set_led_color(0, LED_COLOR_LOW_BATTERY, LED_EFFECT_PULSE);
    printf("Trim: Fitting curves...\n");
}

static void trim_feedback_complete(void) {
    // Green solid - success
    feedback_state = FEEDBACK_EXIT_SUCCESS;
    feedback_start_time = to_ms_since_boot(get_absolute_time());
    status_set_led_color(0, LED_COLOR_READY, LED_EFFECT_SOLID);
    printf("Trim: Calibration complete and saved!\n");
}

static void trim_feedback_error(void) {
    // Fast red blinking - error
    feedback_state = FEEDBACK_EXIT_ERROR;
    feedback_start_time = to_ms_since_boot(get_absolute_time());
    status_set_led_color(0, LED_COLOR_ERROR, LED_EFFECT_BLINK_FAST);
    printf("Trim: ERROR - Not enough samples to save (need at least 5)\n");
}

// Calculate simple checksum
static uint32_t calculate_checksum(const trim_data_flash_t *data) {
    uint32_t sum = data->magic + data->num_samples;
    for (uint8_t i = 0; i < data->num_samples && i < MAX_TRIM_SAMPLES; i++) {
        sum += data->samples[i].speed_percent + data->samples[i].turn_offset;
    }
    return sum;
}

// Get flash memory pointer
static const trim_data_flash_t* get_flash_trim_data(void) {
    return (const trim_data_flash_t*)(XIP_BASE + FLASH_TARGET_OFFSET);
}

// Comparison function for qsort
static int compare_samples_by_speed(const void *a, const void *b) {
    const trim_sample_t *sa = (const trim_sample_t*)a;
    const trim_sample_t *sb = (const trim_sample_t*)b;
    return sa->speed_percent - sb->speed_percent;
}

// Calculate mean of turn offsets
static float calculate_mean(const trim_sample_t *samples, uint8_t count) {
    if (count == 0) return 0.0f;
    float sum = 0.0f;
    for (uint8_t i = 0; i < count; i++) {
        sum += samples[i].turn_offset;
    }
    return sum / count;
}

// Calculate standard deviation of turn offsets
static float calculate_stddev(const trim_sample_t *samples, uint8_t count, float mean) {
    if (count < 2) return 0.0f;
    float sum_sq = 0.0f;
    for (uint8_t i = 0; i < count; i++) {
        float diff = samples[i].turn_offset - mean;
        sum_sq += diff * diff;
    }
    return sqrtf(sum_sq / (count - 1));
}

// Remove outliers from a set of samples
static uint8_t remove_outliers(trim_sample_t *samples, uint8_t count) {
    if (count < 3) return count; // Need at least 3 samples for outlier detection

    float mean = calculate_mean(samples, count);
    float stddev = calculate_stddev(samples, count, mean);

    if (stddev < 0.1f) return count; // All samples very similar, no outliers

    uint8_t new_count = 0;
    float threshold = OUTLIER_THRESHOLD * stddev;

    for (uint8_t i = 0; i < count; i++) {
        float diff = fabsf(samples[i].turn_offset - mean);
        if (diff <= threshold) {
            samples[new_count++] = samples[i];
        } else {
            printf("Trim: Removed outlier: speed=%d, offset=%d (diff=%.1f > %.1f)\n",
                   samples[i].speed_percent, samples[i].turn_offset, diff, threshold);
        }
    }

    return new_count;
}

// Downsample if too many samples
static uint8_t downsample(trim_sample_t *samples, uint8_t count, uint8_t target_count) {
    if (count <= target_count) return count;

    // Sort by speed first
    qsort(samples, count, sizeof(trim_sample_t), compare_samples_by_speed);

    trim_sample_t downsampled[MAX_TRIM_SAMPLES];
    uint8_t new_count = 0;

    // Always keep first and last
    downsampled[new_count++] = samples[0];

    // Calculate step size to get approximately target_count samples
    float step = (float)(count - 1) / (target_count - 1);

    for (uint8_t i = 1; i < target_count - 1; i++) {
        uint8_t idx = (uint8_t)(i * step + 0.5f);
        if (idx < count) {
            downsampled[new_count++] = samples[idx];
        }
    }

    // Always keep last
    downsampled[new_count++] = samples[count - 1];

    // Copy back
    memcpy(samples, downsampled, new_count * sizeof(trim_sample_t));

    printf("Trim: Downsampled from %d to %d samples\n", count, new_count);
    return new_count;
}

bool trim_mode_fit_curves(void) {
    printf("\n=== FITTING TRIM CURVES ===\n");

    if (num_samples < MIN_SAMPLES_TO_SAVE) {
        printf("Error: Not enough samples (%d < %d)\n", num_samples, MIN_SAMPLES_TO_SAVE);
        return false;
    }

    trim_feedback_fitting();

    // Step 1: Remove near-zero speeds
    uint8_t cleaned_count = 0;
    for (uint8_t i = 0; i < num_samples; i++) {
        if (abs(samples[i].speed_percent) >= MIN_SPEED_THRESHOLD) {
            fitted_samples[cleaned_count++] = samples[i];
        }
    }
    printf("After removing near-zero speeds: %d samples\n", cleaned_count);

    if (cleaned_count < MIN_SAMPLES_TO_SAVE) {
        printf("Error: Not enough samples after cleanup\n");
        return false;
    }

    // Step 2: Separate forward and reverse samples
    trim_sample_t forward_samples[MAX_TRIM_SAMPLES];
    trim_sample_t reverse_samples[MAX_TRIM_SAMPLES];
    uint8_t forward_count = 0;
    uint8_t reverse_count = 0;

    for (uint8_t i = 0; i < cleaned_count; i++) {
        if (fitted_samples[i].speed_percent > 0) {
            forward_samples[forward_count++] = fitted_samples[i];
        } else {
            reverse_samples[reverse_count++] = fitted_samples[i];
        }
    }

    printf("Forward samples: %d, Reverse samples: %d\n", forward_count, reverse_count);

    // Step 3: Remove outliers from each direction
    if (forward_count > 2) {
        forward_count = remove_outliers(forward_samples, forward_count);
        printf("After outlier removal - Forward: %d\n", forward_count);
    }

    if (reverse_count > 2) {
        reverse_count = remove_outliers(reverse_samples, reverse_count);
        printf("After outlier removal - Reverse: %d\n", reverse_count);
    }

    // Step 4: Downsample if needed
    if (forward_count > MAX_SAMPLES_PER_DIRECTION) {
        forward_count = downsample(forward_samples, forward_count, 15);
    }

    if (reverse_count > MAX_SAMPLES_PER_DIRECTION) {
        reverse_count = downsample(reverse_samples, reverse_count, 15);
    }

    // Step 5: Combine and sort all samples
    num_fitted_samples = 0;
    for (uint8_t i = 0; i < reverse_count; i++) {
        fitted_samples[num_fitted_samples++] = reverse_samples[i];
    }
    for (uint8_t i = 0; i < forward_count; i++) {
        fitted_samples[num_fitted_samples++] = forward_samples[i];
    }

    // Sort all samples by speed
    qsort(fitted_samples, num_fitted_samples, sizeof(trim_sample_t), compare_samples_by_speed);

    printf("Final fitted samples: %d\n", num_fitted_samples);
    for (uint8_t i = 0; i < num_fitted_samples; i++) {
        printf("  [%d] speed=%d, offset=%d\n", i,
               fitted_samples[i].speed_percent,
               fitted_samples[i].turn_offset);
    }

    printf("=== CURVE FITTING COMPLETE ===\n\n");
    return true;
}

bool trim_mode_init(void) {
    trim_state = TRIM_MODE_INACTIVE;
    num_samples = 0;
    num_fitted_samples = 0;
    memset(samples, 0, sizeof(samples));
    memset(fitted_samples, 0, sizeof(fitted_samples));

    // Try to load saved trim from flash
    if (trim_mode_load()) {
        printf("Trim mode: Loaded %d trim samples from flash\n", num_fitted_samples);
    } else {
        printf("Trim mode: No valid trim data found, starting fresh\n");
    }

    return true;
}

bool trim_mode_load(void) {
    const trim_data_flash_t *flash_data = get_flash_trim_data();

    // Validate magic number
    if (flash_data->magic != TRIM_MAGIC_V2) {
        return false;
    }

    // Validate sample count
    if (flash_data->num_samples > MAX_TRIM_SAMPLES) {
        return false;
    }

    // Validate checksum
    if (flash_data->checksum != calculate_checksum(flash_data)) {
        return false;
    }

    // Load the samples into fitted_samples (these are already cleaned)
    num_fitted_samples = flash_data->num_samples;
    memcpy(fitted_samples, flash_data->samples, num_fitted_samples * sizeof(trim_sample_t));

    return true;
}

bool trim_mode_save(void) {
    if (num_fitted_samples == 0) {
        printf("Trim mode: No samples to save\n");
        return false;
    }

    trim_data_flash_t data = {
        .magic = TRIM_MAGIC_V2,
        .num_samples = num_fitted_samples,
        .reserved = {0, 0, 0},
        .checksum = 0
    };

    // Copy fitted samples
    memcpy(data.samples, fitted_samples, num_fitted_samples * sizeof(trim_sample_t));

    // Calculate checksum
    data.checksum = calculate_checksum(&data);

    // Prepare buffer (must be 256-byte aligned for flash write)
    uint8_t buffer[FLASH_PAGE_SIZE];
    memset(buffer, 0xFF, FLASH_PAGE_SIZE);
    memcpy(buffer, &data, sizeof(trim_data_flash_t));

    // Disable interrupts during flash operation
    uint32_t ints = save_and_disable_interrupts();

    // Erase the sector
    flash_range_erase(FLASH_TARGET_OFFSET, FLASH_SECTOR_SIZE);

    // Write the page
    flash_range_program(FLASH_TARGET_OFFSET, buffer, FLASH_PAGE_SIZE);

    // Re-enable interrupts
    restore_interrupts(ints);

    printf("Trim mode: Saved %d samples to flash\n", num_fitted_samples);
    return true;
}

void trim_mode_handle_exit_feedback(void) {
    // Handle exit feedback timeout - restore to normal connected state
    if (feedback_state == FEEDBACK_EXIT_SUCCESS || feedback_state == FEEDBACK_EXIT_ERROR) {
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now - feedback_start_time > FEEDBACK_EXIT_DURATION_MS) {
            // Exit feedback complete, restore normal connected status
            feedback_state = FEEDBACK_NONE;
            status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
        }
    }
}

void trim_mode_check_activation(trim_gamepad_ptr gp_ptr) {
#if !DIAGNOSTIC_MODE_BUILD
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
                num_samples = 0; // Clear working samples
                feedback_state = FEEDBACK_NONE; // Reset feedback state

                printf("\n=== DYNAMIC TRIM CALIBRATION MODE ===\n");
                printf("Drive normally with full control\n");
                printf("- Press A button to capture trim sample\n");
                printf("- Press B button to remove last sample\n");
                printf("- Collect 5+ samples at various speeds\n");
                printf("- Hold L3+R3 for 2s to fit curves and exit\n\n");

                // Set LED to show trim mode (blinking to indicate active)
                status_set_system(SYSTEM_STATUS_TEST_MODE, LED_EFFECT_BLINK_MEDIUM);
                status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

            } else {
                // Exit trim mode - fit curves and save
                trim_state = TRIM_MODE_INACTIVE;
                feedback_state = FEEDBACK_NONE; // Reset feedback state

                printf("\n=== EXITING TRIM MODE ===\n");
                printf("Collected %d samples\n", num_samples);

                // Fit curves with collected samples
                if (trim_mode_fit_curves()) {
                    trim_mode_save();
                    trim_feedback_complete();
                    printf("Trim mode: Saved successfully\n");
                } else {
                    trim_feedback_error();
                    printf("Trim mode: Not enough samples, trim not saved\n");
                }

                printf("Returning to normal operation.\n\n");

                // LED feedback stays visible through normal status updates
                // The success/error LED state will remain until next mode change
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
#endif // !DIAGNOSTIC_MODE_BUILD
}

void trim_mode_capture_sample(int8_t forward, int8_t turn) {
    if (num_samples >= MAX_TRIM_SAMPLES) {
        printf("Trim: Sample buffer full (%d samples)\n", MAX_TRIM_SAMPLES);
        trim_feedback_error();
        return;
    }

    samples[num_samples].speed_percent = forward;
    samples[num_samples].turn_offset = turn;
    num_samples++;

    printf("Trim: Captured sample #%d: speed=%d, offset=%d\n",
           num_samples, forward, turn);

    trim_feedback_captured();
}

void trim_mode_remove_last_sample(void) {
    if (num_samples == 0) {
        printf("Trim: No samples to remove\n");
        return;
    }

    num_samples--;
    printf("Trim: Removed sample #%d (now %d samples)\n",
           num_samples + 1, num_samples);

    trim_feedback_removed();
}

bool trim_mode_update(trim_gamepad_ptr gp_ptr) {
    if (trim_state == TRIM_MODE_INACTIVE) {
        return false;
    }

#if !DIAGNOSTIC_MODE_BUILD
    uni_gamepad_t *gp = (uni_gamepad_t*)gp_ptr;

    // Check for A button press (capture sample)
    bool button_a = (gp->buttons & BTN_A) != 0;
    if (button_a && !button_a_prev) {
        // A button just pressed - this is handled in bluetooth_platform.c
        // because it needs the current drive state
    }
    button_a_prev = button_a;

    // Check for B button press (remove last sample)
    bool button_b = (gp->buttons & BTN_B) != 0;
    if (button_b && !button_b_prev) {
        trim_mode_remove_last_sample();
    }
    button_b_prev = button_b;

    // Handle feedback flash timeout - restore normal trim mode LED state
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if (feedback_state != FEEDBACK_NONE && feedback_state != FEEDBACK_EXIT_SUCCESS && feedback_state != FEEDBACK_EXIT_ERROR) {
        if (now - feedback_start_time > FEEDBACK_FLASH_DURATION_MS) {
            // Flash complete, restore blinking purple trim mode state
            feedback_state = FEEDBACK_NONE;
            status_set_system(SYSTEM_STATUS_TEST_MODE, LED_EFFECT_BLINK_MEDIUM);
        }
    }

    // Status output
    static uint32_t last_print = 0;
    if (now - last_print > 1000) {
        printf("Trim mode: %d samples collected (Press A to capture, B to remove last)\n",
               num_samples);
        last_print = now;
    }
#endif // !DIAGNOSTIC_MODE_BUILD

    return true;  // Trim mode is active
}

bool trim_mode_is_active(void) {
    return trim_state == TRIM_MODE_ACTIVE;
}

int8_t trim_mode_get_offset(int8_t speed_percent) {
    // If no fitted samples, return 0
    if (num_fitted_samples == 0) {
        return 0;
    }

    // If only one sample, return its offset
    if (num_fitted_samples == 1) {
        return fitted_samples[0].turn_offset;
    }

    // Piecewise linear interpolation
    // Samples are sorted by speed_percent

    // If speed is below all samples, use first sample's offset
    if (speed_percent <= fitted_samples[0].speed_percent) {
        return fitted_samples[0].turn_offset;
    }

    // If speed is above all samples, use last sample's offset
    if (speed_percent >= fitted_samples[num_fitted_samples - 1].speed_percent) {
        return fitted_samples[num_fitted_samples - 1].turn_offset;
    }

    // Find the two nearest samples (one below, one above)
    for (uint8_t i = 0; i < num_fitted_samples - 1; i++) {
        if (speed_percent >= fitted_samples[i].speed_percent &&
            speed_percent <= fitted_samples[i + 1].speed_percent) {

            // Linear interpolation
            int8_t speed1 = fitted_samples[i].speed_percent;
            int8_t speed2 = fitted_samples[i + 1].speed_percent;
            int8_t offset1 = fitted_samples[i].turn_offset;
            int8_t offset2 = fitted_samples[i + 1].turn_offset;

            // Handle case where speeds are equal (shouldn't happen with cleaned data)
            if (speed1 == speed2) {
                return offset1;
            }

            // Linear interpolate: offset = offset1 + (offset2-offset1) * (speed-speed1)/(speed2-speed1)
            float factor = (float)(speed_percent - speed1) / (float)(speed2 - speed1);
            float interpolated = offset1 + (offset2 - offset1) * factor;

            return (int8_t)(interpolated + 0.5f); // Round to nearest
        }
    }

    // Fallback (should not reach here)
    return 0;
}

void trim_mode_reset(void) {
    num_samples = 0;
    num_fitted_samples = 0;
    memset(samples, 0, sizeof(samples));
    memset(fitted_samples, 0, sizeof(fitted_samples));
    trim_mode_save();
    printf("Trim reset: All samples cleared\n");
}
