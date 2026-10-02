#ifndef DRIVE_HBRIDGE_H
#define DRIVE_HBRIDGE_H

// Drive motors on two Pololu DRV8874 carriers driven directly by the Pico.
//
// Each motor is driven in PWM (IN/IN) mode with slow decay ("drive/brake"):
// speed follows duty almost linearly and zero command brakes the motor (the
// drag-brake fraction mixes brake and coast).  The carrier's SLEEP pin is held
// low (outputs off, coasting) until a controller is ready.
//
// The ADC samples both current-sense outputs and the battery divider
// continuously (round robin, DMA ring buffer), so nothing in the control path
// waits on a conversion.  From duty, battery voltage and motor current the
// module estimates each motor's back-EMF (wheel speed).  The winding
// resistance the estimate needs is measured on each start from rest, and then,
// more accurately, on every drive -> brake transition (stick released).
//
// Each motor also learns how fast it turns for a given duty.  A damaged drive
// train (dragging gearbox) shows up as a lower gain than the other side: it is
// reported as degraded (console event, controller rumble) and every motor's
// duty is scaled so the robot still drives straight and turns evenly.

#include <stdbool.h>
#include <stdint.h>

#include "motor_control.h"

typedef struct {
    int16_t target_permille;     // commanded duty, -1000..1000
    int16_t applied_permille;    // after the acceleration limit
    uint16_t current_ma;         // motor current magnitude (current sense)
    int32_t emf_mv;              // estimated back-EMF, signed
    int32_t wheel_rpm;           // emf_mv scaled by DRIVE_MOTOR_RPM_PER_V
    bool emf_valid;              // false while coasting (not observable)
    bool overridden;             // HITL duty override active
    uint16_t match_scale_permille; // speed matching scale applied to the target
    uint16_t health_permille;    // speed gain vs the other motor, worst bin (1000 = equal or better)
    bool degraded;               // health below DRIVE_HEALTH_ALERT
    uint16_t roughness_permille; // current jitter / mean while steady
    uint16_t derate_permille;    // HITL artificial weakness (1000 = none)
    uint32_t resistance_mohm;    // current winding-resistance estimate
    uint32_t resistance_samples; // start-from-rest measurements taken
    uint32_t resistance_run_samples; // drive->brake (running) measurements; these take over
} drive_hb_motor_t;

typedef struct {
    drive_hb_motor_t motor[2];   // MOTOR_LEFT_DRIVE, MOTOR_RIGHT_DRIVE
    uint32_t battery_mv;
    bool awake;
    bool fault;                  // nFAULT asserted now
    uint32_t fault_events;       // nFAULT falling edges seen
    uint16_t accel_limit_pct_s;  // 0 = off
    uint16_t drag_brake_permille;
    bool match_enabled;
    uint32_t degraded_events;
} drive_hb_status_t;

bool drive_hb_init(void);
// Duty for a drive motor, -1000..1000 (sign = OUT1->OUT2 direction).
void drive_hb_set(motor_channel_t motor, int16_t duty_permille);
// Outputs enabled (SLEEP high) or asleep (coasting).
void drive_hb_set_awake(bool awake);
// Periodic: acceleration limit, estimation, fault edge counting.
void drive_hb_update(void);
void drive_hb_get_status(drive_hb_status_t* out);
uint32_t drive_hb_battery_mv(void);

// Runtime tuning (HITL / tests); persist only until reboot.
void drive_hb_set_accel_limit(uint16_t pct_per_s);
void drive_hb_set_drag_brake(uint16_t permille);
// Coasts one motor for duration_ms so its terminal voltage shows the true
// back-EMF (ground truth for the estimate).  Prints the estimate taken just
// before the window.
bool drive_hb_probe(motor_channel_t motor, uint16_t duration_ms);
// HITL: hold a motor at a fixed duty, ignoring drive_hb_set(), until cleared
// or the driver sleeps.  Still subject to the acceleration limit.
void drive_hb_set_override(motor_channel_t motor, bool enabled, int16_t duty_permille);
// Speed matching (on by default, DRIVE_MATCH_ENABLED) and its learned state.
void drive_hb_set_match(bool enabled);
void drive_hb_reset_learning(void);
void drive_hb_print_learning(void);
// HITL: only this fraction of the duty reaches the motor, to simulate a weak
// or damaged drive train repeatably.  The control logic does not know.
void drive_hb_set_derate(motor_channel_t motor, uint16_t permille);

// HITL: prints the last `samples` raw current-sense readings of a motor
// (0 = as many as the ring safely holds, ~16 ms).
void drive_hb_dump_current(motor_channel_t motor, uint32_t samples);

#endif  // DRIVE_HBRIDGE_H
