#ifndef DRIVE_H
#define DRIVE_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    int8_t forward;
    int8_t turn;
    bool enabled;
} drive_control_t;

typedef struct {
    int8_t left_speed;
    int8_t right_speed;
} drive_output_t;

bool drive_init(void);
void drive_update(drive_control_t* control);
drive_output_t drive_mix(int8_t forward, int8_t turn);
void drive_stop(void);
void drive_set_expo(uint8_t expo_value);
int8_t drive_apply_expo(int8_t input, uint8_t expo);

#endif // DRIVE_H