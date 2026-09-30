#include "dshot.h"
#include "dshot_rx.h"
#include "config.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "pico/stdlib.h"
#include "pico/mutex.h"
#include <stdio.h>
#include <string.h>

// Include generated PIO headers
#include "dshot.pio.h"

#define MAX_DSHOT_MOTORS 3
#define DSHOT_FRAME_BITS 16
#define DSHOT_THROTTLE_MIN 48    // Below 48 = disarmed
#define DSHOT_THROTTLE_MAX 2047
#define EDT_FRAME_BITS 21        // EDT telemetry frame size
#define DSHOT_BIDIR_CLKDIV_SCALE 1.0f
// Per-motor DShot state
typedef struct {
    bool initialized;
    dshot_config_t config;
    PIO pio;
    uint sm;                    // State machine ID
    uint pio_offset;            // PIO program offset
    int dma_chan;               // DMA channel for transmission
    dshot_telemetry_t last_telemetry;
    uint32_t last_packet;       // Last transmitted packet (left-aligned for MSB-first shift)
    int8_t crc_invert_override; // -1 = use config, 0 = normal, 1 = invert
    bool edt_active;            // ESC acknowledged EDT enable (0xE00) or sent EDT frames
    bool edt_seen;              // any EDT frame decoded since init / enable
    uint32_t telem_type_counts[16];   // valid frames by payload type nibble (value >> 8)
    dshot_rx_stats_t rx_stats;
} dshot_motor_state_t;

static dshot_motor_state_t motor_states[MAX_DSHOT_MOTORS] = {0};

// Reference counting for shared PIO programs
// Multiple motors may share the same PIO program, so track usage
static uint8_t pio_program_refcount_tx = 0;
static uint8_t pio_program_refcount_bidir = 0;

// Mutex for thread-safe PIO reference counting
// Refcounts are modified during init/deinit and must be protected from races
static mutex_t pio_refcount_mutex;
static bool pio_mutex_initialized = false;

// CRC-4 calculation for DShot packets (xor of three nibbles)
uint8_t dshot_calculate_crc(uint16_t packet) {
    // DShot checksum is XOR of the 3 nibbles in the 12-bit payload
    return (packet ^ (packet >> 4) ^ (packet >> 8)) & 0x0F;
}

// Convert percent (-100 to +100) to DShot throttle value
uint16_t dshot_throttle_from_percent(int8_t percent) {
    if (percent == 0) {
        return 0;  // Disarmed
    }

    // Map percent [-100, +100] to throttle [MIN, MAX] using linear interpolation
    // Uses (percent + 100) to avoid negative intermediates that would underflow
    int32_t throttle_range = DSHOT_THROTTLE_MAX - DSHOT_THROTTLE_MIN;  // 1999
    int32_t normalized_percent = (int32_t)percent + 100;  // 0 to 200
    int32_t value = DSHOT_THROTTLE_MIN + (normalized_percent * throttle_range) / 200;

    // Clamp to valid range (defensive, should not be needed with correct formula)
    if (value < DSHOT_THROTTLE_MIN) value = DSHOT_THROTTLE_MIN;
    if (value > DSHOT_THROTTLE_MAX) value = DSHOT_THROTTLE_MAX;

    return (uint16_t)value;
}

uint16_t dshot_throttle_from_percent_unidir(uint8_t percent) {
    if (percent == 0) {
        return 0;
    }

    percent = (uint8_t)CLAMP(percent, 0, 100);
    int32_t throttle_range = DSHOT_THROTTLE_MAX - DSHOT_THROTTLE_MIN;
    int32_t value = DSHOT_THROTTLE_MIN + ((int32_t)percent * throttle_range) / 100;

    if (value < DSHOT_THROTTLE_MIN) {
        value = DSHOT_THROTTLE_MIN;
    }
    if (value > DSHOT_THROTTLE_MAX) {
        value = DSHOT_THROTTLE_MAX;
    }

    return (uint16_t)value;
}

// DShot 3D mode throttle ranges
#define DSHOT_3D_REVERSE_MIN 48
#define DSHOT_3D_REVERSE_MAX 1047
#define DSHOT_3D_FORWARD_MIN 1048
#define DSHOT_3D_FORWARD_MAX 2047

uint16_t dshot_throttle_from_percent_3d(int8_t percent) {
    if (percent == 0) {
        return 0;  // Stop
    }

    if (percent > 0) {
        // Forward: +1..+100 → 1048..2047
        int32_t range = DSHOT_3D_FORWARD_MAX - DSHOT_3D_FORWARD_MIN;  // 999
        int32_t value = DSHOT_3D_FORWARD_MIN + ((int32_t)percent * range) / 100;
        if (value < DSHOT_3D_FORWARD_MIN) value = DSHOT_3D_FORWARD_MIN;
        if (value > DSHOT_3D_FORWARD_MAX) value = DSHOT_3D_FORWARD_MAX;
        return (uint16_t)value;
    } else {
        // Reverse: -1..-100 → 48..1047 (more negative = higher throttle in reverse)
        int32_t mag = -percent;  // 1..100
        int32_t range = DSHOT_3D_REVERSE_MAX - DSHOT_3D_REVERSE_MIN;  // 999
        int32_t value = DSHOT_3D_REVERSE_MIN + (mag * range) / 100;
        if (value < DSHOT_3D_REVERSE_MIN) value = DSHOT_3D_REVERSE_MIN;
        if (value > DSHOT_3D_REVERSE_MAX) value = DSHOT_3D_REVERSE_MAX;
        return (uint16_t)value;
    }
}

// Encode DShot packet with CRC
static uint16_t encode_dshot_packet(uint16_t throttle, bool telemetry_request, bool invert_crc) {
    // Packet format (16 bits transmitted MSB first):
    // [15:5] = 11-bit throttle (0-2047)
    // [4]    = 1-bit telemetry request
    // [3:0]  = 4-bit CRC (calculated on bits [15:4])

    // Place throttle in final position [15:5]
    uint16_t packet = (throttle & 0x7FF) << 5;

    // Place telemetry request in final position [4]
    packet |= (telemetry_request ? 1 : 0) << 4;

    // CRC covers the 12-bit payload (bits [15:4])
    uint8_t crc = dshot_calculate_crc(packet >> 4);
    if (invert_crc) {
        crc = (uint8_t)(~crc) & 0x0F;
    }

    // Add CRC to bits [3:0]
    packet |= (crc & 0x0F);

    return packet;
}

// Calculate PIO clock divider for DShot speed
static float calculate_clk_div(dshot_speed_t speed) {
    uint32_t sys_clk_hz = clock_get_hz(clk_sys);

    // Bit period in nanoseconds
    uint32_t bit_period_ns;
    switch (speed) {
        case DSHOT_SPEED_150:  bit_period_ns = 6670; break;
        case DSHOT_SPEED_300:  bit_period_ns = 3330; break;
        case DSHOT_SPEED_600:  bit_period_ns = 1670; break;
        case DSHOT_SPEED_1200: bit_period_ns = 830;  break;
        default: bit_period_ns = 3330; break;
    }

    // PIO program uses 16 cycles per bit (both bit-1 and bit-0 paths)
    uint32_t cycles_per_bit = 16;

    // pio_freq = (1 MHz * cycles_per_bit * 1000) / bit_period_ns
    // uint64_t required: intermediate exceeds uint32_t max
    uint64_t pio_freq_hz = (1000000ULL * cycles_per_bit * 1000ULL) / bit_period_ns;

    float clk_div = (float)sys_clk_hz / (float)pio_freq_hz;

    // Clamp to valid range (1.0 to 65536.0)
    if (clk_div < 1.0f) clk_div = 1.0f;
    if (clk_div > 65536.0f) clk_div = 65536.0f;

    return clk_div;
}

static void telemetry_reset(dshot_motor_state_t* state) {
    memset(&state->last_telemetry, 0, sizeof(state->last_telemetry));
    state->edt_active = false;
    state->edt_seen = false;
}

// Applies one decoded frame to the per-field telemetry.  Only the field the
// frame carries is updated, and its time recorded, so consumers can tell a
// new voltage from one left over from seconds ago.
static void apply_frame(dshot_motor_state_t* state, const dshot_frame_t* f, uint32_t now_ms) {
    dshot_telemetry_t* t = &state->last_telemetry;
    t->fresh = 0;
    t->type = (uint8_t)f->kind;
    t->value = f->raw;
    t->valid = true;
    t->timestamp_ms = now_ms;
    state->telem_type_counts[(f->raw >> 8) & 0x0F]++;
    state->rx_stats.kinds[f->kind]++;

    switch (f->kind) {
    case DSHOT_FRAME_ERPM:
        t->erpm = f->erpm;
        t->stopped = false;
        t->erpm_ms = now_ms;
        t->fresh |= DSHOT_FRESH_ERPM;
        break;
    case DSHOT_FRAME_STOPPED:
        t->erpm = 0;
        t->stopped = true;
        t->erpm_ms = now_ms;
        t->fresh |= DSHOT_FRESH_ERPM;
        break;
    case DSHOT_FRAME_VOLT:
        t->voltage_cV = (uint16_t)f->data * 25;
        t->voltage_ms = now_ms;
        t->fresh |= DSHOT_FRESH_VOLT;
        state->edt_seen = true;
        break;
    case DSHOT_FRAME_CURR:
        t->current_cA = (uint16_t)f->data * DSHOT_EDT_CURRENT_CA_PER_STEP;
        t->current_ms = now_ms;
        t->fresh |= DSHOT_FRESH_CURR;
        state->edt_seen = true;
        break;
    case DSHOT_FRAME_TEMP:
        t->temperature_C = f->data;
        t->temperature_ms = now_ms;
        t->fresh |= DSHOT_FRESH_TEMP;
        state->edt_seen = true;
        break;
    case DSHOT_FRAME_EVENT:
        t->fresh |= DSHOT_FRESH_EVENT;
        if (f->raw == 0xE00) {
            state->rx_stats.edt_enabled_events++;
            state->edt_active = true;
        } else if (f->raw == 0xEFF) {
            state->rx_stats.edt_disabled_events++;
            state->edt_active = false;
        }
        break;
    default:
        // Debug / stress frames: counted, not otherwise used.
        break;
    }
    if (state->edt_seen) {
        state->edt_active = true;
    }
}

// Initialize DShot for a motor
bool dshot_init(motor_channel_t motor, const dshot_config_t* config) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS || config == NULL) {
        DEBUG_PRINT("CRITICAL: Invalid parameters in dshot_init\n");
        return false;
    }

    if (config->gpio_pin >= 30) {
        DEBUG_PRINT("CRITICAL: Invalid GPIO pin %d\n", config->gpio_pin);
        return false;
    }

    // Validate GCR decode table on first initialization
    if (!pio_mutex_initialized) {
        mutex_init(&pio_refcount_mutex);
        pio_mutex_initialized = true;
    }

    dshot_motor_state_t* state = &motor_states[motor];

    // Copy configuration
    memcpy(&state->config, config, sizeof(dshot_config_t));

    // Select PIO instance (use PIO0 for all motors, different state machines)
    state->pio = pio0;

    // Dynamically allocate state machine to avoid race with WS2812
    state->sm = pio_claim_unused_sm(state->pio, true);
    if (state->sm == (uint)-1) {
        DEBUG_PRINT("ERROR: No PIO state machines available\n");
        return false;
    }

    // Check if we can add the PIO program
    if (!pio_can_add_program(state->pio, config->bidirectional ? &dshot_bidirectional_program : &dshot_tx_program)) {
        DEBUG_PRINT("ERROR: Cannot add DShot PIO program (no space)\n");
        pio_sm_unclaim(state->pio, state->sm);
        return false;
    }

    // Add PIO program with reference counting; mutex protects refcounts
    mutex_enter_blocking(&pio_refcount_mutex);

    if (config->bidirectional) {
        if (pio_program_refcount_bidir == 0) {
            state->pio_offset = pio_add_program(state->pio, &dshot_bidirectional_program);
        } else {
            // Reuse existing program offset from another initialized motor
            bool found = false;
            for (int i = 0; i < MAX_DSHOT_MOTORS; i++) {
                if (motor_states[i].initialized && motor_states[i].config.bidirectional) {
                    state->pio_offset = motor_states[i].pio_offset;
                    found = true;
                    break;
                }
            }
            if (!found) {
                DEBUG_PRINT("CRITICAL: PIO bidir refcount=%d but no program found!\n",
                           pio_program_refcount_bidir);
                mutex_exit(&pio_refcount_mutex);
                pio_sm_unclaim(state->pio, state->sm);
                return false;
            }
        }
        pio_program_refcount_bidir++;
        mutex_exit(&pio_refcount_mutex);

        float clk_div = calculate_clk_div(config->speed);
        clk_div *= DSHOT_BIDIR_CLKDIV_SCALE;
        dshot_bidirectional_program_init(state->pio, state->sm, state->pio_offset,
                                         config->gpio_pin, clk_div);
    } else {
        if (pio_program_refcount_tx == 0) {
            state->pio_offset = pio_add_program(state->pio, &dshot_tx_program);
        } else {
            // Reuse existing program offset from another initialized motor
            bool found = false;
            for (int i = 0; i < MAX_DSHOT_MOTORS; i++) {
                if (motor_states[i].initialized && !motor_states[i].config.bidirectional) {
                    state->pio_offset = motor_states[i].pio_offset;
                    found = true;
                    break;
                }
            }
            if (!found) {
                DEBUG_PRINT("CRITICAL: PIO tx refcount=%d but no program found!\n",
                           pio_program_refcount_tx);
                mutex_exit(&pio_refcount_mutex);
                pio_sm_unclaim(state->pio, state->sm);
                return false;
            }
        }
        pio_program_refcount_tx++;
        mutex_exit(&pio_refcount_mutex);

        dshot_tx_program_init(state->pio, state->sm, state->pio_offset,
                              config->gpio_pin, calculate_clk_div(config->speed));
    }

    // Allocate DMA channel
    state->dma_chan = dma_claim_unused_channel(true);
    if (state->dma_chan < 0) {
        DEBUG_PRINT("ERROR: No DMA channels available\n");
        // Clean up PIO program on DMA allocation failure
        mutex_enter_blocking(&pio_refcount_mutex);
        if (config->bidirectional) {
            pio_program_refcount_bidir--;
            if (pio_program_refcount_bidir == 0) {
                pio_remove_program(state->pio, &dshot_bidirectional_program, state->pio_offset);
            }
        } else {
            pio_program_refcount_tx--;
            if (pio_program_refcount_tx == 0) {
                pio_remove_program(state->pio, &dshot_tx_program, state->pio_offset);
            }
        }
        mutex_exit(&pio_refcount_mutex);
        pio_sm_unclaim(state->pio, state->sm);

        // Initialize fields individually (safer than memset on partial struct)
        state->initialized = false;
        state->pio = NULL;
        state->sm = 0;
        state->pio_offset = 0;
        state->dma_chan = -1;
        state->last_packet = 0;
        telemetry_reset(state);
        return false;
    }

    // Configure DMA for PIO TX FIFO
    dma_channel_config dma_config = dma_channel_get_default_config(state->dma_chan);
    channel_config_set_transfer_data_size(&dma_config, DMA_SIZE_32);  // 32-bit transfers
    channel_config_set_read_increment(&dma_config, false);            // Read from same location (packet)
    channel_config_set_write_increment(&dma_config, false);           // Write to PIO FIFO
    channel_config_set_dreq(&dma_config, pio_get_dreq(state->pio, state->sm, true));  // Paced by PIO TX

    dma_channel_configure(
        state->dma_chan,
        &dma_config,
        &state->pio->txf[state->sm],  // Write to PIO TX FIFO
        NULL,                          // Read address set per-transfer
        1,                             // Transfer 1 word (16-bit packet)
        false                          // Don't start yet
    );

    // Initialize telemetry
    telemetry_reset(state);
    memset(state->telem_type_counts, 0, sizeof(state->telem_type_counts));
    memset(&state->rx_stats, 0, sizeof(state->rx_stats));
    state->crc_invert_override = -1;
    state->initialized = true;

    DEBUG_PRINT("DShot initialized: motor=%d, GPIO=%d, speed=%d, bidir=%d, PIO=%p, SM=%d, DMA=%d\n",
           motor, config->gpio_pin, config->speed, config->bidirectional,
           state->pio, state->sm, state->dma_chan);

    return true;
}

// Send throttle command via DShot
bool dshot_send_throttle(motor_channel_t motor, uint16_t throttle, bool request_telemetry) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        DEBUG_PRINT("WARNING: DShot not initialized for motor %d\n", motor);
        return false;
    }

    // NULL pointer checks before dereferencing
    if (state->pio == NULL) {
        DEBUG_PRINT("CRITICAL: NULL PIO pointer for motor %d\n", motor);
        return false;
    }

    if (state->dma_chan < 0) {
        DEBUG_PRINT("CRITICAL: Invalid DMA channel for motor %d\n", motor);
        return false;
    }

    // Clamp throttle to valid range
    if (throttle > DSHOT_THROTTLE_MAX) {
        throttle = DSHOT_THROTTLE_MAX;
    }

    // Encode packet
    bool invert_crc = state->config.bidirectional;
    if (state->crc_invert_override >= 0) {
        invert_crc = (state->crc_invert_override != 0);
    }
    uint16_t packet = encode_dshot_packet(throttle, request_telemetry, invert_crc);
    // Left-align 16-bit packet so MSB shifts out first with left-shift OSR.
    state->last_packet = ((uint32_t)packet) << 16;

    // Timeout for DMA waits (generous for ~53μs DShot300 frame)
    #define DSHOT_DMA_TIMEOUT_MS 50

    // Check if previous transfer is still active; timeout avoids infinite hang
    // when PIO is stalled (e.g. RX FIFO full in bidirectional mode).
    if (dma_channel_is_busy(state->dma_chan)) {
        DEBUG_PRINT("WARNING: DShot DMA still busy for motor %d, waiting...\n", motor);
        uint32_t wait_start = to_ms_since_boot(get_absolute_time());
        while (dma_channel_is_busy(state->dma_chan)) {
            if ((to_ms_since_boot(get_absolute_time()) - wait_start) > DSHOT_DMA_TIMEOUT_MS) {
                DEBUG_PRINT("CRITICAL: Previous DMA hung for motor %d, aborting\n", motor);
                dma_channel_abort(state->dma_chan);
                busy_wait_us(10);
                break;
            }
            tight_loop_contents();
        }
    }

    // Drain RX FIFO to prevent PIO backpressure stall (bidirectional mode).
    // In bidirectional DShot, PIO captures an RX response after every TX frame.
    // The RX FIFO is only 4 words deep (2 frames). If not drained, PIO stalls
    // which blocks DREQ, causing the next DMA transfer to hang indefinitely.
    if (state->config.bidirectional) {
        while (pio_sm_get_rx_fifo_level(state->pio, state->sm) > 0) {
            (void)pio_sm_get(state->pio, state->sm);
            state->rx_stats.discarded_words++;
        }
        state->rx_stats.frames_sent++;
    }

    // Check PIO TX FIFO level - should have space for at least 1 word
    uint8_t fifo_level = pio_sm_get_tx_fifo_level(state->pio, state->sm);
    if (fifo_level >= 4) {  // FIFO is 4 words deep
        DEBUG_PRINT("WARNING: DShot PIO FIFO full for motor %d, clearing...\n", motor);
        pio_sm_clear_fifos(state->pio, state->sm);
    }

    // Configure DMA to transfer packet to PIO
    dma_channel_set_read_addr(state->dma_chan, &state->last_packet, false);
    dma_channel_set_trans_count(state->dma_chan, 1, false);

    // Start DMA transfer
    dma_channel_start(state->dma_chan);

    // Timeout instead of blocking wait — prevents hang if DMA fails during e-stop
    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    bool timeout = false;

    while (dma_channel_is_busy(state->dma_chan)) {
        if ((to_ms_since_boot(get_absolute_time()) - start_time) > DSHOT_DMA_TIMEOUT_MS) {
            timeout = true;
            break;
        }
        tight_loop_contents();  // Yield to other code
    }

    if (timeout) {
        DEBUG_PRINT("CRITICAL: DMA timeout for motor %d, aborting transfer\n", motor);
        dma_channel_abort(state->dma_chan);
        // Wait for abort to complete (should be fast)
        uint32_t abort_start = to_ms_since_boot(get_absolute_time());
        while (dma_channel_is_busy(state->dma_chan)) {
            if ((to_ms_since_boot(get_absolute_time()) - abort_start) > 10) {
                DEBUG_PRINT("ERROR: DMA abort failed for motor %d\n", motor);
                break;
            }
            tight_loop_contents();
        }
        return false;
    }

    // Verify DMA transfer completed (transfer_count == 0)
    uint32_t remaining = dma_channel_hw_addr(state->dma_chan)->transfer_count;
    if (remaining != 0) {
        DEBUG_PRINT("ERROR: DMA transfer incomplete for motor %d (remaining=%u)\n", motor, remaining);
        return false;
    }

    // PIO will drain the TX FIFO autonomously (~53µs for a DShot300 frame).
    // No need to block here — the next send will check for DMA/FIFO readiness.

    return true;
}

// ============================================================================
// ADVANCED DSHOT FEATURES (Not currently used - for future ESC integration)
// ============================================================================
// The following functions implement advanced DShot protocol features:
// - Special ESC commands (beep, reverse, save settings, etc.)
// - Bidirectional EDT telemetry (voltage, current, temperature, RPM)
// - ESC configuration via DShot protocol
//
// These are complete implementations kept for future use when:
// - Weapon system switches to DShot mode permanently
// - EDT telemetry is integrated into safety monitoring
// - Advanced ESC control is needed
//
// NOTE: DShot is now enabled by default for weapon motor.
// ============================================================================

// Send DShot command (must be repeated 6+ times)
bool dshot_send_command(motor_channel_t motor, dshot_command_t cmd) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    // DShot commands must be sent 6-10 times with small delays
    for (int i = 0; i < 10; i++) {
        if (!dshot_send_throttle(motor, (uint16_t)cmd, false)) {
            return false;
        }
        sleep_ms(2);
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (state->initialized) {
        if (cmd == DSHOT_CMD_EXTENDED_TELEMETRY_DISABLE) {
            state->edt_active = false;
            state->edt_seen = false;
        }
    }

    return true;
}

// Read one raw reply capture (bidirectional mode only).  The PIO pushes all
// DSHOT_RX_WORDS words of a capture back to back, so a partial FIFO means a
// capture is still in progress.
bool dshot_read_telemetry_raw(motor_channel_t motor, uint32_t words[DSHOT_RX_WORDS]) {
    if (motor >= MAX_DSHOT_MOTORS || words == NULL) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    if (pio_sm_get_rx_fifo_level(state->pio, state->sm) < DSHOT_RX_WORDS) {
        return false;
    }

    for (int i = 0; i < DSHOT_RX_WORDS; i++) {
        words[i] = pio_sm_get(state->pio, state->sm);
    }
    state->rx_stats.replies_read++;
    return true;
}

// Reads and decodes one reply.  Returns true when a valid frame was decoded;
// telemetry then holds the updated snapshot and its fresh mask says which
// field the frame carried.
bool dshot_read_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry) {
    if (motor >= MAX_DSHOT_MOTORS || telemetry == NULL) {
        return false;
    }

    uint32_t words[DSHOT_RX_WORDS];
    if (!dshot_read_telemetry_raw(motor, words)) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    uint16_t value = 0;
    dshot_rx_result_t res = dshot_rx_decode_samples(words, &value);
    state->rx_stats.results[res]++;
    if (res != DSHOT_RX_OK) {
        return false;
    }

    dshot_frame_t frame;
    dshot_rx_classify(value, &frame);
    apply_frame(state, &frame, to_ms_since_boot(get_absolute_time()));
    memcpy(telemetry, &state->last_telemetry, sizeof(dshot_telemetry_t));
    return true;
}

bool dshot_get_rx_stats(motor_channel_t motor, dshot_rx_stats_t* stats) {
    if (motor >= MAX_DSHOT_MOTORS || stats == NULL || !motor_states[motor].initialized) {
        return false;
    }
    memcpy(stats, &motor_states[motor].rx_stats, sizeof(*stats));
    return true;
}

void dshot_reset_rx_stats(motor_channel_t motor) {
    if (motor < MAX_DSHOT_MOTORS) {
        memset(&motor_states[motor].rx_stats, 0, sizeof(motor_states[motor].rx_stats));
    }
}

// Get last valid telemetry
bool dshot_get_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS || telemetry == NULL) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->last_telemetry.valid) {
        return false;
    }

    // Reject stale telemetry — may indicate ESC communication loss
    uint32_t age_ms = to_ms_since_boot(get_absolute_time()) - state->last_telemetry.timestamp_ms;
    #define TELEMETRY_MAX_AGE_MS 100
    if (age_ms > TELEMETRY_MAX_AGE_MS) {
        DEBUG_PRINT("WARNING: Telemetry stale (%u ms old) for motor %d\n", age_ms, motor);
        return false;
    }

    memcpy(telemetry, &state->last_telemetry, sizeof(dshot_telemetry_t));
    return true;
}

bool dshot_extended_telemetry_active(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    return state->edt_active;
}

bool dshot_extended_telemetry_seen(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    return state->edt_seen;
}

bool dshot_sm_is_enabled(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || state->pio == NULL) {
        return false;
    }

    return (state->pio->ctrl & (1u << state->sm)) != 0;
}

bool dshot_get_fifo_levels(motor_channel_t motor, uint8_t* tx_level, uint8_t* rx_level) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || state->pio == NULL) {
        return false;
    }

    if (tx_level != NULL) {
        *tx_level = pio_sm_get_tx_fifo_level(state->pio, state->sm);
    }
    if (rx_level != NULL) {
        *rx_level = pio_sm_get_rx_fifo_level(state->pio, state->sm);
    }

    return true;
}

void dshot_get_telemetry_type_counts(motor_channel_t motor, uint32_t counts[16]) {
    if (motor >= MAX_DSHOT_MOTORS || counts == NULL) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        memset(counts, 0, sizeof(uint32_t) * 16);
        return;
    }

    memcpy(counts, state->telem_type_counts, sizeof(state->telem_type_counts));
}

void dshot_reset_telemetry_type_counts(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    memset(state->telem_type_counts, 0, sizeof(state->telem_type_counts));
}

// Convert eRPM to actual RPM
uint32_t dshot_erpm_to_rpm(uint32_t erpm, uint8_t pole_pairs) {
    if (pole_pairs == 0) {
        DEBUG_PRINT("WARNING: Invalid pole_pairs=0 in dshot_erpm_to_rpm\n");
        return 0;
    }
    return erpm / pole_pairs;
}

// Deinitialize DShot (free resources)
void dshot_deinit(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    // Stop and disable state machine
    pio_sm_set_enabled(state->pio, state->sm, false);

    // Unclaim state machine
    pio_sm_unclaim(state->pio, state->sm);

    // Remove PIO program only if this is the last user; mutex protects refcounts
    mutex_enter_blocking(&pio_refcount_mutex);
    if (state->config.bidirectional) {
        pio_program_refcount_bidir--;
        if (pio_program_refcount_bidir == 0) {
            pio_remove_program(state->pio, &dshot_bidirectional_program, state->pio_offset);
        }
    } else {
        pio_program_refcount_tx--;
        if (pio_program_refcount_tx == 0) {
            pio_remove_program(state->pio, &dshot_tx_program, state->pio_offset);
        }
    }
    mutex_exit(&pio_refcount_mutex);

    // Cleanup DMA channel before unclaiming
    if (state->dma_chan >= 0) {
        // Abort any active DMA transfer
        dma_channel_abort(state->dma_chan);
        // Wait for abort to complete
        dma_channel_wait_for_finish_blocking(state->dma_chan);
        // Now safe to unclaim
        dma_channel_unclaim(state->dma_chan);
    }

    // Clear state
    memset(state, 0, sizeof(dshot_motor_state_t));
    state->dma_chan = -1;
    state->crc_invert_override = -1;

    DEBUG_PRINT("DShot deinitialized for motor %d\n", motor);
}

void dshot_set_crc_invert_override(motor_channel_t motor, int8_t invert) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    if (invert < -1) invert = -1;
    if (invert > 1) invert = 1;
    state->crc_invert_override = invert;
}
