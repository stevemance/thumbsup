#ifndef TEST_MODE_H
#define TEST_MODE_H

#include <stdbool.h>
#include <stdint.h>

// Opaque pointer type - actual type defined in uni.h
typedef void* test_mode_gamepad_ptr;

// Test mode state management
void test_mode_init(void);
bool test_mode_is_active(void);
void test_mode_check_activation(test_mode_gamepad_ptr gp);
void test_mode_update(test_mode_gamepad_ptr gp);

#endif // TEST_MODE_H