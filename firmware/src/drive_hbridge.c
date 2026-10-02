#include "drive_hbridge.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "bluetooth_platform.h"
#include "config.h"
#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "pico/stdlib.h"

// ---------------------------------------------------------------------------
// ADC: free-running round robin over ADC0 (left CS), ADC1 (right CS) and
// ADC2 (battery), DMA'd into a ring.  Sample k belongs to input k % 3.
// ---------------------------------------------------------------------------
#define ADC_RING_SAMPLES 1024
#define ADC_INPUTS 3
#define ADC_IN_CS_LEFT 0
#define ADC_IN_CS_RIGHT 1
#define ADC_IN_BATTERY 2
// 48 MHz / (1 + div): ~57 kS/s total, ~19 kS/s per input.  Deliberately not a
// divisor of the 20 kHz PWM, so averages do not alias onto the PWM ripple.
#define ADC_CLKDIV 841.0f
#define ADC_TOTAL_HZ (48000000.0f / (1.0f + ADC_CLKDIV))
#define ADC_VOLTS_PER_COUNT (3.3f / 4096.0f)

static uint16_t adc_ring[ADC_RING_SAMPLES] __attribute__((aligned(ADC_RING_SAMPLES * sizeof(uint16_t))));
static int adc_dma = -1;
static uint16_t cs_offset_counts[2];

static inline uint32_t adc_samples_written(void) {
    return 0xFFFFFFFFu - dma_hw->ch[adc_dma].transfer_count;
}

// Mean of the last n samples of one input, ending at (and including) sample
// index `end_excl - 1`.
static float adc_mean(uint32_t input, uint32_t end_excl, uint32_t n) {
    uint32_t sum = 0, got = 0;
    uint32_t k = end_excl;
    while (got < n && k > 0 && end_excl - k < ADC_RING_SAMPLES - ADC_INPUTS) {
        k--;
        if (k % ADC_INPUTS == input) {
            sum += adc_ring[k % ADC_RING_SAMPLES] & 0x0FFF;
            got++;
        }
    }
    return got ? (float)sum / (float)got : 0.0f;
}

// Peak of one input's 3-sample moving average over sample indices [from, to).
// Used for currents that settle with the motor's L/R time constant (~0.4 ms).
static float adc_peak_range(uint32_t input, uint32_t from, uint32_t to, uint32_t* count) {
    uint16_t w[3] = {0, 0, 0};
    uint32_t got = 0;
    float peak = 0.0f;
    for (uint32_t k = from; k < to; k++) {
        if (k % ADC_INPUTS != input) {
            continue;
        }
        w[got % 3] = adc_ring[k % ADC_RING_SAMPLES] & 0x0FFF;
        got++;
        if (got >= 3) {
            float m = (w[0] + w[1] + w[2]) / 3.0f;
            if (m > peak) peak = m;
        }
    }
    *count = got;
    return peak;
}

static void adc_start(void) {
    adc_init();
    adc_gpio_init(PIN_HB_CS_LEFT);
    adc_gpio_init(PIN_HB_CS_RIGHT);
    adc_gpio_init(PIN_BATTERY_ADC);
    adc_run(false);
    adc_select_input(0);
    adc_set_round_robin(0x7);
    adc_fifo_setup(true, true, 1, false, false);
    adc_set_clkdiv(ADC_CLKDIV);
    adc_fifo_drain();

    adc_dma = dma_claim_unused_channel(true);
    dma_channel_config c = dma_channel_get_default_config(adc_dma);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_16);
    channel_config_set_read_increment(&c, false);
    channel_config_set_write_increment(&c, true);
    channel_config_set_ring(&c, true, 11);   // 2^11 bytes = ADC_RING_SAMPLES samples
    channel_config_set_dreq(&c, DREQ_ADC);
    dma_channel_configure(adc_dma, &c, adc_ring, &adc_hw->fifo, 0xFFFFFFFFu, true);
    adc_run(true);
}

// ---------------------------------------------------------------------------
// PWM: IN1/IN2 of a motor share one slice, so both inputs switch together.
// ---------------------------------------------------------------------------
static const uint8_t in_pins[2][2] = {
    {PIN_HB_LEFT_IN1, PIN_HB_LEFT_IN2},
    {PIN_HB_RIGHT_IN1, PIN_HB_RIGHT_IN2},
};
static uint16_t pwm_full;   // level for "always high" (wrap + 1)

typedef struct {
    int16_t target;          // permille
    float applied;           // permille, after the acceleration limit
    float emf_v;             // filtered back-EMF estimate
    bool emf_valid;
    float current_a;
    float resistance;        // ohms
    uint32_t resistance_samples;
    uint32_t zero_since_ms;  // command has been 0 since
    bool rcal_pending;
    uint32_t rcal_start_sample;
    float rcal_duty;
    float rcal_vbatt;
    // running resistance from a drive -> brake transition
    bool brcal_pending;
    uint32_t brcal_start_sample;
    float brcal_vm;          // average motor voltage while driving
    float brcal_irun;        // motoring current just before the brake
    uint32_t brcal_samples;
    uint64_t probe_until_us;
    bool overridden;
    float derate;            // HITL: fraction of the duty that reaches the motor
    float match_scale;       // speed matching: target is multiplied by this
    // steady-state tracking for learning
    float steady_target;
    float steady_s;
    float cur_mean;          // current mean / mean square while steady (roughness)
    float cur_msq;
    float roughness;
} motor_state_t;

// ---------------------------------------------------------------------------
// Wheel health and speed matching.
//
// Each motor learns, per direction and per duty bin, its speed gain: back-EMF
// per volt applied, i.e. how fast it turns for a given duty.  A healthy free
// wheel sits near 0.85-0.9; a dragging gearbox is lower, and it gets worse with
// speed.  Matching slows whichever wheel is faster for its current command so
// the wheel speeds keep the ratio the stick asked for (straight stays
// straight) when one side is damaged.  Duty is only ever reduced.
// ---------------------------------------------------------------------------
#define GAIN_BINS 8
#define GAIN_BIN_WIDTH (1.0f / GAIN_BINS)
static const float gain_bin_center[GAIN_BINS] = {0.125f, 0.25f, 0.375f, 0.5f, 0.625f, 0.75f, 0.875f, 1.0f};
static float gain[2][2][GAIN_BINS];       // [motor][dir: 0 = +, 1 = -][bin]
static uint32_t gain_n[2][2][GAIN_BINS];  // learning updates taken
static bool match_enabled = DRIVE_MATCH_ENABLED;
static float health[2] = {1.0f, 1.0f};
static bool degraded[2] = {false, false};
static uint32_t below_since_ms[2] = {0, 0};   // health under the alert level since (0 = not)
static uint32_t degraded_events = 0;

static motor_state_t mot[2];
static bool initialized = false;
static bool awake = false;
static bool fault_prev = false;
static uint32_t fault_events = 0;
static uint16_t accel_limit_pct_s = DRIVE_ACCEL_LIMIT_PCT_PER_S;
static uint16_t drag_brake = DRIVE_DRAG_BRAKE_PERMILLE;
static float battery_v = 0.0f;
static uint64_t last_update_us = 0;

static int idx_of(motor_channel_t m) {
    return m == MOTOR_RIGHT_DRIVE ? 1 : 0;
}

static void set_levels(int i, uint16_t in1, uint16_t in2) {
    pwm_set_gpio_level(in_pins[i][0], in1);
    pwm_set_gpio_level(in_pins[i][1], in2);
}

// Duty that actually reaches the motor (permille, motor frame before the
// wiring inversion).
static float effective_duty(const motor_state_t* s) {
    return s->applied * s->derate;
}

static void write_outputs(int i) {
    motor_state_t* s = &mot[i];
    if (s->probe_until_us && time_us_64() < s->probe_until_us) {
        set_levels(i, 0, 0);                                   // coast
        return;
    }
    s->probe_until_us = 0;
    int32_t d = (int32_t)lrintf(effective_duty(s));
    if (i == 0 ? DRIVE_HB_LEFT_INVERT : DRIVE_HB_RIGHT_INVERT) {
        d = -d;
    }
    if (d > 0) {
        // IN1 high, IN2 high for the brake fraction: forward / brake.
        set_levels(i, pwm_full, (uint16_t)((int32_t)pwm_full * (1000 - d) / 1000));
    } else if (d < 0) {
        set_levels(i, (uint16_t)((int32_t)pwm_full * (1000 + d) / 1000), pwm_full);
    } else {
        // Both inputs together: high = brake, low = coast.
        uint16_t level = (uint16_t)((uint32_t)pwm_full * drag_brake / 1000);
        set_levels(i, level, level);
    }
}

// Applies the acceleration limit.  Slowing down and reversing through zero
// are never delayed; only an increase in speed is rate limited.
static void step_applied(int i, float dt_s) {
    motor_state_t* s = &mot[i];
    float target = (float)s->target * s->match_scale;
    float applied = s->applied;
    if (applied != 0.0f && (target == 0.0f || (target > 0.0f) != (applied > 0.0f))) {
        applied = 0.0f;                                        // stop / reverse: instant
    }
    if (fabsf(target) <= fabsf(applied)) {
        applied = target;                                      // decelerating: instant
    } else if (accel_limit_pct_s == 0) {
        applied = target;
    } else {
        float step = (float)accel_limit_pct_s * 10.0f * dt_s;   // permille
        float diff = target - applied;
        applied += fabsf(diff) <= step ? diff : copysignf(step, diff);
    }
    s->applied = applied;
}

bool drive_hb_init(void) {
    if (initialized) {
        return true;
    }
    memset(mot, 0, sizeof(mot));

    gpio_init(PIN_HB_SLEEP);
    gpio_set_dir(PIN_HB_SLEEP, GPIO_OUT);
    gpio_put(PIN_HB_SLEEP, 0);
    gpio_init(PIN_HB_FAULT);
    gpio_set_dir(PIN_HB_FAULT, GPIO_IN);
    gpio_pull_up(PIN_HB_FAULT);

    uint32_t wrap = clock_get_hz(clk_sys) / DRIVE_HB_PWM_HZ - 1;
    pwm_full = (uint16_t)(wrap + 1);
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_clkdiv(&cfg, 1.0f);
    pwm_config_set_wrap(&cfg, (uint16_t)wrap);
    uint32_t slice_mask = 0;
    for (int i = 0; i < 2; i++) {
        for (int j = 0; j < 2; j++) {
            gpio_set_function(in_pins[i][j], GPIO_FUNC_PWM);
            uint slice = pwm_gpio_to_slice_num(in_pins[i][j]);
            pwm_init(slice, &cfg, false);
            slice_mask |= 1u << slice;
        }
    }
    for (int i = 0; i < 2; i++) {
        mot[i].resistance = DRIVE_MOTOR_R_OHM;
        mot[i].derate = 1.0f;
        mot[i].match_scale = 1.0f;
        set_levels(i, 0, 0);
    }
    pwm_set_mask_enabled(pwm_hw->en | slice_mask);

    adc_start();
    sleep_ms(5);
    // Drivers are asleep, so the current-sense outputs read zero current.
    uint32_t end = adc_samples_written();
    cs_offset_counts[0] = (uint16_t)adc_mean(ADC_IN_CS_LEFT, end, 64);
    cs_offset_counts[1] = (uint16_t)adc_mean(ADC_IN_CS_RIGHT, end, 64);

    last_update_us = time_us_64();
    initialized = true;
    return true;
}

void drive_hb_set_awake(bool on) {
    if (!initialized || on == awake) {
        return;
    }
    awake = on;
    gpio_put(PIN_HB_SLEEP, on ? 1 : 0);
    if (!on) {
        for (int i = 0; i < 2; i++) {
            mot[i].overridden = false;
            mot[i].target = 0;
            mot[i].applied = 0.0f;
            write_outputs(i);
        }
    }
}

// Learned gain of motor i in direction dir at duty magnitude a (0..1):
// linear between the nearest learned bins on either side, or the nearest
// learned bin alone when it is within one bin width.  Returns 0 (unknown)
// otherwise: gain changes with speed (friction dominates slow), so it is
// never extrapolated far.
static float gain_at(int i, int dir, float a) {
    float lo_c = -1.0f, lo_g = 0.0f, hi_c = -1.0f, hi_g = 0.0f;
    for (int b = 0; b < GAIN_BINS; b++) {
        if (gain_n[i][dir][b] < DRIVE_MATCH_MIN_SAMPLES) {
            continue;
        }
        float c = gain_bin_center[b];
        if (c <= a) {
            lo_c = c;
            lo_g = gain[i][dir][b];
        } else if (hi_c < 0.0f) {
            hi_c = c;
            hi_g = gain[i][dir][b];
        }
    }
    bool lo_ok = lo_c >= 0.0f && a - lo_c <= GAIN_BIN_WIDTH + 1e-3f;
    bool hi_ok = hi_c >= 0.0f && hi_c - a <= GAIN_BIN_WIDTH + 1e-3f;
    if (lo_ok && hi_ok) return lo_g + (hi_g - lo_g) * (a - lo_c) / (hi_c - lo_c);
    if (lo_ok) return lo_g;
    if (hi_ok) return hi_g;
    return 0.0f;
}

// Scale for motor i's target so the two wheels' speeds keep the ratio the
// stick asked for: each motor is compared with the other at the direction
// and duty the other is commanded right now, and only the faster one (for
// its command) is slowed.  No correction while the other motor is stopped
// (pivoting) or either gain is not learned near the commanded duty.
static float match_scale_for(int i, int16_t target) {
    int16_t other_target = mot[1 - i].target;
    if (!match_enabled || target == 0 || other_target == 0) {
        return 1.0f;
    }
    float a = fabsf((float)target) / 1000.0f;
    float own = gain_at(i, target > 0 ? 0 : 1, a);
    float other = gain_at(1 - i, other_target > 0 ? 0 : 1, fabsf((float)other_target) / 1000.0f);
    if (own <= 0.0f || other <= 0.0f || other >= own) {
        return 1.0f;
    }
    // Want a' * gain(a') = a * other.  First order assumes gain is flat in
    // duty; refined with the learned gain at the reduced duty once that is
    // known (the reduced duty gets learned once the motor runs there).
    float scale = other / own;
    float g = gain_at(i, target > 0 ? 0 : 1, a * scale);
    if (g > 0.0f) {
        scale = other / g;
    }
    if (scale > 1.0f - DRIVE_MATCH_DEADBAND) {
        return 1.0f;
    }
    return scale < DRIVE_MATCH_MIN_SCALE ? DRIVE_MATCH_MIN_SCALE : (scale > 1.0f ? 1.0f : scale);
}

// Learns motor i's gain while its command has been steady long enough for
// the wheel to reach speed.  Samples that look stalled or pinned (very low
// gain) are skipped: that is the arena, not the gearbox.
static void learn_gain(int i, float dt) {
    motor_state_t* s = &mot[i];
    float a = fabsf(s->applied) / 1000.0f;
    // Steady = same command (matching may still nudge the applied duty).
    if ((float)s->target != s->steady_target || s->target == 0 || !s->emf_valid ||
        fabsf(s->applied - (float)s->target * s->match_scale) > 1.0f) {
        s->steady_target = (float)s->target;
        s->steady_s = 0.0f;
        return;
    }
    s->steady_s += dt;
    // Roughness: current jitter while steady (grinding gearbox).
    float beta = dt / (DRIVE_HEALTH_ROUGH_S + dt);
    if (s->steady_s < DRIVE_MATCH_STEADY_S) {
        s->cur_mean = s->current_a;
        s->cur_msq = s->current_a * s->current_a;
        return;
    }
    s->cur_mean += beta * (s->current_a - s->cur_mean);
    s->cur_msq += beta * (s->current_a * s->current_a - s->cur_msq);
    float var = s->cur_msq - s->cur_mean * s->cur_mean;
    s->roughness = s->cur_mean > 0.02f && var > 0.0f ? sqrtf(var) / s->cur_mean : 0.0f;

    if (a < gain_bin_center[0] - GAIN_BIN_WIDTH / 2 || battery_v < 5.0f) {
        return;
    }
    // Motor frame: emf and applied duty have the same sign when turning the
    // commanded way (wiring inversion applies to both).
    float sample = s->emf_v / (s->applied / 1000.0f * battery_v);
    if ((i == 0 ? DRIVE_HB_LEFT_INVERT : DRIVE_HB_RIGHT_INVERT)) {
        sample = -sample;
    }
    if (sample < DRIVE_MATCH_MIN_GAIN || sample > 1.2f) {
        return;
    }
    int dir = s->applied > 0.0f ? 0 : 1;
    int b = (int)lrintf(a * GAIN_BINS) - 1;
    if (b < 0) b = 0;
    if (b >= GAIN_BINS) b = GAIN_BINS - 1;
    if (fabsf(a - gain_bin_center[b]) > GAIN_BIN_WIDTH / 2 + 1e-3f) {
        return;
    }
    if (gain_n[i][dir][b] == 0) {
        gain[i][dir][b] = sample;
    } else {
        gain[i][dir][b] += dt / (DRIVE_MATCH_LEARN_S + dt) * (sample - gain[i][dir][b]);
    }
    gain_n[i][dir][b]++;
}

// Health: each motor's gain relative to the other motor driving the robot
// the same way (left + pairs with right -, as the motors face each other),
// worst bin.  Raises a console event and a controller rumble on degradation.
static void update_health(void) {
    for (int i = 0; i < 2; i++) {
        float worst = 1.0f;
        for (int dir = 0; dir < 2; dir++) {
            int other_dir = DRIVE_HB_MOTORS_FACE_EACH_OTHER ? 1 - dir : dir;
            for (int b = 0; b < GAIN_BINS; b++) {
                // Slow bins are dominated by static friction and scatter.
                if (gain_bin_center[b] < DRIVE_HEALTH_MIN_DUTY ||
                    gain_n[i][dir][b] < DRIVE_MATCH_MIN_SAMPLES ||
                    gain_n[1 - i][other_dir][b] < DRIVE_MATCH_MIN_SAMPLES) {
                    continue;
                }
                float r = gain[i][dir][b] / gain[1 - i][other_dir][b];
                if (r < worst) worst = r;
            }
        }
        health[i] = worst;
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        if (worst >= DRIVE_HEALTH_ALERT) {
            below_since_ms[i] = 0;
        } else if (below_since_ms[i] == 0) {
            below_since_ms[i] = now_ms ? now_ms : 1;
        }
        bool persistent = below_since_ms[i] && now_ms - below_since_ms[i] >= DRIVE_HEALTH_PERSIST_MS;
        if (!degraded[i] && persistent) {
            degraded[i] = true;
            degraded_events++;
#if SERIAL_GAMEPAD
            bool rumbled = false;                              // no Bluetooth controller
#else
            bool rumbled = bluetooth_platform_controller_rumble(DRIVE_HEALTH_RUMBLE_MS, 255, 255);
#endif
            printf("DRV HEALTH motor=%c level=DEGRADED ratio=%.3f rumble=%u\n", i == 0 ? 'L' : 'R', worst,
                   rumbled ? 1u : 0u);
        } else if (degraded[i] && worst > DRIVE_HEALTH_ALERT + DRIVE_HEALTH_HYST) {
            degraded[i] = false;
            printf("DRV HEALTH motor=%c level=OK ratio=%.3f\n", i == 0 ? 'L' : 'R', worst);
        }
    }
}

static void apply_target(int i, int16_t duty_permille) {
    motor_state_t* s = &mot[i];
    if (duty_permille > 1000) duty_permille = 1000;
    if (duty_permille < -1000) duty_permille = -1000;

    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    bool was_zero = (s->target == 0 && s->applied == 0.0f);
    float prev_duty = effective_duty(s);
    bool was_steady = s->steady_s >= DRIVE_BRCAL_STEADY_S;
    bool at_rest = was_zero && (now_ms - s->zero_since_ms) >= DRIVE_REST_MS &&
                   (!s->emf_valid || fabsf(s->emf_v) < DRIVE_REST_EMF_V);
    s->target = duty_permille;
    if (duty_permille == 0 && !was_zero) {
        s->zero_since_ms = now_ms;
    }
    s->match_scale = match_scale_for(i, duty_permille);
    step_applied(i, 0.0f);                                     // instant parts now
    write_outputs(i);

    // Winding resistance: right after a start from rest the motor has no
    // back-EMF yet, so current = duty * Vbatt / R.
    if (at_rest && awake && fabsf(effective_duty(s)) >= DRIVE_RCAL_MIN_DUTY && battery_v > 5.0f) {
        s->rcal_pending = true;
        s->rcal_start_sample = adc_samples_written();
        s->rcal_duty = fabsf(effective_duty(s)) / 1000.0f;
        s->rcal_vbatt = battery_v;
    }

    // Running resistance: just before a full brake the motor draws
    // I_run = (V - emf) / R; just after, shorted, it carries I_brake = emf / R
    // at the same speed.  Their sum is V / R whatever the emf, and both are
    // measured at speed, averaged over many commutator positions.
    if (duty_permille == 0 && was_steady && awake && drag_brake >= 1000 && !s->probe_until_us &&
        fabsf(prev_duty) >= DRIVE_BRCAL_MIN_DUTY && battery_v > 5.0f && s->current_a > 0.05f) {
        uint32_t written = adc_samples_written();
        float counts = adc_mean((uint32_t)i, written, 19) - (float)cs_offset_counts[i];
        s->brcal_irun = counts * ADC_VOLTS_PER_COUNT / DRIVE_HB_CS_VOLTS_PER_AMP;
        s->brcal_vm = fabsf(prev_duty) / 1000.0f * battery_v;
        s->brcal_start_sample = written;
        s->brcal_pending = true;
    }
}

void drive_hb_set(motor_channel_t m, int16_t duty_permille) {
    if (!initialized || (m != MOTOR_LEFT_DRIVE && m != MOTOR_RIGHT_DRIVE)) {
        return;
    }
    int i = idx_of(m);
    if (!mot[i].overridden) {
        apply_target(i, duty_permille);
    }
}

void drive_hb_set_override(motor_channel_t m, bool enabled, int16_t duty_permille) {
    if (!initialized || (m != MOTOR_LEFT_DRIVE && m != MOTOR_RIGHT_DRIVE)) {
        return;
    }
    int i = idx_of(m);
    mot[i].overridden = false;
    apply_target(i, enabled ? duty_permille : 0);
    mot[i].overridden = enabled;
}

static void finish_brcal(int i, uint32_t written) {
    motor_state_t* s = &mot[i];
    uint32_t from = s->brcal_start_sample + (uint32_t)(DRIVE_BRCAL_FROM_US * 1e-6f * ADC_TOTAL_HZ);
    uint32_t to = s->brcal_start_sample + (uint32_t)(DRIVE_BRCAL_TO_US * 1e-6f * ADC_TOTAL_HZ);
    if (written < to + ADC_INPUTS) {
        return;
    }
    s->brcal_pending = false;
    if (written - from > ADC_RING_SAMPLES - 2 * ADC_INPUTS || s->target != 0) {
        return;                                                // overwritten, or driven again
    }
    // The brake current reverses through zero and settles with the L/R time
    // constant while the wheel has barely slowed: its peak is emf / R.
    uint32_t n = 0;
    float counts = adc_peak_range((uint32_t)i, from, to, &n) - (float)cs_offset_counts[i];
    float i_brake = counts * ADC_VOLTS_PER_COUNT / DRIVE_HB_CS_VOLTS_PER_AMP;
    if (n < 3 || i_brake < 0.05f || i_brake > DRIVE_RCAL_MAX_A || s->brcal_irun < 0.03f) {
        return;
    }
    float r = s->brcal_vm / (s->brcal_irun + i_brake);
    if (r < 1.0f || r > 30.0f) {
        return;
    }
    // Takes over from the start-from-rest value once measured.
    s->resistance = s->brcal_samples == 0 ? r : s->resistance + DRIVE_BRCAL_ALPHA * (r - s->resistance);
    s->brcal_samples++;
}

static void finish_rcal(int i, uint32_t written) {
    motor_state_t* s = &mot[i];
    uint32_t from = s->rcal_start_sample + (uint32_t)(DRIVE_RCAL_FROM_US * 1e-6f * ADC_TOTAL_HZ);
    uint32_t to = s->rcal_start_sample + (uint32_t)(DRIVE_RCAL_TO_US * 1e-6f * ADC_TOTAL_HZ);
    if (written < to + ADC_INPUTS) {
        return;                                                // window not sampled yet
    }
    s->rcal_pending = false;
    if (written - from > ADC_RING_SAMPLES - 2 * ADC_INPUTS) {
        return;                                                // too late: overwritten
    }
    // The current rises with the L/R time constant, then falls as the wheel
    // picks up speed: its peak is close to V / R.
    uint32_t n = 0;
    float counts = adc_peak_range((uint32_t)i, from, to, &n) - (float)cs_offset_counts[i];
    float amps = counts * ADC_VOLTS_PER_COUNT / DRIVE_HB_CS_VOLTS_PER_AMP;
    if (n < 3 || amps < 0.2f || amps > DRIVE_RCAL_MAX_A) {
        return;                                                // too small, or current-limited
    }
    float r = s->rcal_duty * s->rcal_vbatt / amps;
    if (r < 1.0f || r > 30.0f) {
        return;
    }
    s->resistance_samples++;
    if (s->brcal_samples == 0) {
        s->resistance = s->resistance_samples == 1 ? r : s->resistance + 0.3f * (r - s->resistance);
    }
}

void drive_hb_update(void) {
    if (!initialized) {
        return;
    }
    uint64_t now_us = time_us_64();
    float dt = (float)(now_us - last_update_us) * 1e-6f;
    last_update_us = now_us;
    if (dt > 0.1f) dt = 0.1f;

    uint32_t written = adc_samples_written();
    battery_v = adc_mean(ADC_IN_BATTERY, written, 32) * ADC_VOLTS_PER_COUNT * BATTERY_DIVIDER;

    // nFAULT also pulses while the current limit chops (pushing, stalls), so
    // the log is rate limited; every edge is counted.
    static uint64_t last_fault_log_us = 0;
    bool fault = !gpio_get(PIN_HB_FAULT);
    if (fault != fault_prev) {
        if (fault) {
            fault_events++;
        }
        if (now_us - last_fault_log_us >= 100000) {
            printf(fault ? "DRV FAULT asserted (events=%lu)\n" : "DRV FAULT cleared (events=%lu)\n",
                   (unsigned long)fault_events);
            last_fault_log_us = now_us;
        }
    }
    fault_prev = fault;

    float alpha = dt / (DRIVE_EMF_FILTER_S + dt);
    for (int i = 0; i < 2; i++) {
        motor_state_t* s = &mot[i];
        s->match_scale = match_scale_for(i, s->target);
        step_applied(i, dt);
        write_outputs(i);
        if (s->rcal_pending) {
            finish_rcal(i, written);
        }
        if (s->brcal_pending) {
            finish_brcal(i, written);
        }

        float counts = adc_mean((uint32_t)i, written, 16) - (float)cs_offset_counts[i];
        s->current_a = counts > 0.0f ? counts * ADC_VOLTS_PER_COUNT / DRIVE_HB_CS_VOLTS_PER_AMP : 0.0f;
        if (!awake || s->probe_until_us) {
            continue;
        }

        // Back-EMF from the motor model.  IPROPI only sees current flowing
        // down through a low-side FET: motoring current is seen all cycle,
        // generating (regenerative) current only in the brake part, scaled by
        // (1 - |d|).  The current-sense output is a magnitude, so of the two
        // readings the one that keeps the estimate continuous wins.
        float d = effective_duty(s) / 1000.0f;
        if (i == 0 ? DRIVE_HB_LEFT_INVERT : DRIVE_HB_RIGHT_INVERT) {
            d = -d;
        }
        float ir = s->current_a * s->resistance;
        float e;
        if (d != 0.0f) {
            float vm = d * battery_v;
            float sgn = d > 0.0f ? 1.0f : -1.0f;
            float brake_frac = 1.0f - fabsf(d);
            e = vm - sgn * ir;                                 // motoring
            if (brake_frac > 0.05f) {
                float e_generating = vm + sgn * ir / brake_frac;
                if (fabsf(e_generating - s->emf_v) < fabsf(e - s->emf_v)) {
                    e = e_generating;
                }
            }
        } else if (drag_brake >= 50) {
            // Braking: the shorted winding carries -emf/R, seen for the brake
            // fraction of the cycle.
            float mag = ir * 1000.0f / (float)drag_brake;
            e = s->emf_v >= 0.0f ? mag : -mag;
        } else {
            s->emf_valid = false;                              // coasting: not observable
            continue;
        }
        s->emf_valid = true;
        s->emf_v += alpha * (e - s->emf_v);
        learn_gain(i, dt);
    }
    static uint32_t health_tick = 0;
    if (++health_tick % 50 == 0) {
        update_health();
    }
}

void drive_hb_get_status(drive_hb_status_t* out) {
    memset(out, 0, sizeof(*out));
    for (int i = 0; i < 2; i++) {
        float d = (i == 0 ? DRIVE_HB_LEFT_INVERT : DRIVE_HB_RIGHT_INVERT) ? -1.0f : 1.0f;
        out->motor[i].target_permille = mot[i].target;
        out->motor[i].applied_permille = (int16_t)lrintf(mot[i].applied);
        out->motor[i].current_ma = (uint16_t)(mot[i].current_a * 1000.0f);
        out->motor[i].emf_mv = (int32_t)(mot[i].emf_v * 1000.0f * d);
        out->motor[i].wheel_rpm = (int32_t)(mot[i].emf_v * DRIVE_MOTOR_RPM_PER_V * d);
        out->motor[i].emf_valid = mot[i].emf_valid;
        out->motor[i].overridden = mot[i].overridden;
        out->motor[i].match_scale_permille = (uint16_t)lrintf(mot[i].match_scale * 1000.0f);
        out->motor[i].health_permille = (uint16_t)lrintf(health[i] * 1000.0f);
        out->motor[i].degraded = degraded[i];
        out->motor[i].roughness_permille = (uint16_t)lrintf(mot[i].roughness * 1000.0f);
        out->motor[i].derate_permille = (uint16_t)lrintf(mot[i].derate * 1000.0f);
        out->motor[i].resistance_mohm = (uint32_t)(mot[i].resistance * 1000.0f);
        out->motor[i].resistance_samples = mot[i].resistance_samples;
        out->motor[i].resistance_run_samples = mot[i].brcal_samples;
    }
    out->battery_mv = (uint32_t)(battery_v * 1000.0f);
    out->awake = awake;
    out->fault = fault_prev;
    out->fault_events = fault_events;
    out->accel_limit_pct_s = accel_limit_pct_s;
    out->drag_brake_permille = drag_brake;
    out->match_enabled = match_enabled;
    out->degraded_events = degraded_events;
}

uint32_t drive_hb_battery_mv(void) {
    return (uint32_t)(battery_v * 1000.0f);
}

void drive_hb_set_accel_limit(uint16_t pct_per_s) {
    accel_limit_pct_s = pct_per_s;
}

void drive_hb_set_drag_brake(uint16_t permille) {
    drag_brake = permille > 1000 ? 1000 : permille;
    for (int i = 0; i < 2; i++) {
        write_outputs(i);
    }
}

bool drive_hb_probe(motor_channel_t m, uint16_t duration_ms) {
    if (!initialized || (m != MOTOR_LEFT_DRIVE && m != MOTOR_RIGHT_DRIVE) || duration_ms == 0) {
        return false;
    }
    int i = idx_of(m);
    float d = (i == 0 ? DRIVE_HB_LEFT_INVERT : DRIVE_HB_RIGHT_INVERT) ? -1.0f : 1.0f;
    printf("DRV PROBE motor=%c emf_mv=%ld valid=%u duty=%d current_ma=%u r_mohm=%lu\n",
           i == 0 ? 'L' : 'R', (long)(mot[i].emf_v * 1000.0f * d), mot[i].emf_valid ? 1u : 0u,
           (int)lrintf(mot[i].applied), (unsigned)(mot[i].current_a * 1000.0f),
           (unsigned long)(mot[i].resistance * 1000.0f));
    mot[i].probe_until_us = time_us_64() + (uint64_t)duration_ms * 1000u;
    write_outputs(i);
    return true;
}

void drive_hb_dump_current(motor_channel_t m, uint32_t samples) {
    if (!initialized || (m != MOTOR_LEFT_DRIVE && m != MOTOR_RIGHT_DRIVE)) {
        return;
    }
    uint32_t input = (uint32_t)idx_of(m);
    // The DMA keeps writing while this copies: stay well clear of the write
    // position (~2 ms of samples), or the oldest slots hold the newest data.
    uint32_t max = (ADC_RING_SAMPLES - 128) / ADC_INPUTS;
    if (samples == 0 || samples > max) {
        samples = max;
    }
    // Snapshot first: printing is slow enough for the ring to wrap.
    static uint16_t snap[ADC_RING_SAMPLES / ADC_INPUTS];
    uint32_t end = adc_samples_written();
    uint32_t k = end, got = 0;
    while (got < samples && k > 0) {
        k--;
        if (k % ADC_INPUTS == input) {
            snap[samples - 1 - got] = adc_ring[k % ADC_RING_SAMPLES] & 0x0FFF;
            got++;
        }
    }
    printf("DRV TRACE motor=%c n=%lu period_us=%.2f offset=%u ma_per_count=%.4f data=",
           input == 0 ? 'L' : 'R', (unsigned long)got, 1e6f * ADC_INPUTS / ADC_TOTAL_HZ,
           cs_offset_counts[input], 1000.0f * ADC_VOLTS_PER_COUNT / DRIVE_HB_CS_VOLTS_PER_AMP);
    for (uint32_t j = samples - got; j < samples; j++) {
        printf(j + 1 < samples ? "%u," : "%u", snap[j]);
    }
    printf("\n");
}

void drive_hb_set_match(bool enabled) {
    match_enabled = enabled;
}

void drive_hb_reset_learning(void) {
    memset(gain, 0, sizeof(gain));
    memset(gain_n, 0, sizeof(gain_n));
    for (int i = 0; i < 2; i++) {
        health[i] = 1.0f;
        degraded[i] = false;
        below_since_ms[i] = 0;
        mot[i].match_scale = 1.0f;
    }
}

void drive_hb_set_derate(motor_channel_t m, uint16_t permille) {
    if (m != MOTOR_LEFT_DRIVE && m != MOTOR_RIGHT_DRIVE) {
        return;
    }
    mot[idx_of(m)].derate = (permille > 1000 ? 1000 : permille) / 1000.0f;
}

void drive_hb_print_learning(void) {
    for (int i = 0; i < 2; i++) {
        for (int dir = 0; dir < 2; dir++) {
            printf("DRV GAIN motor=%c dir=%c", i == 0 ? 'L' : 'R', dir == 0 ? '+' : '-');
            for (int b = 0; b < GAIN_BINS; b++) {
                printf(" b%d=%.3f/%lu", (int)lrintf(gain_bin_center[b] * 100.0f), gain[i][dir][b],
                       (unsigned long)gain_n[i][dir][b]);
            }
            printf("\n");
        }
    }
    printf("DRV HEALTH match=%u l_health=%.3f l_degraded=%u l_rough=%.3f r_health=%.3f r_degraded=%u "
           "r_rough=%.3f events=%lu\n", match_enabled ? 1u : 0u, health[0], degraded[0] ? 1u : 0u,
           mot[0].roughness, health[1], degraded[1] ? 1u : 0u, mot[1].roughness,
           (unsigned long)degraded_events);
}
