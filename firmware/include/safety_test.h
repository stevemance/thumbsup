#ifndef SAFETY_TEST_H
#define SAFETY_TEST_H

#include <stdbool.h>

/**
 * Comprehensive safety test suite for ThumbsUp robot
 * Validates all critical safety features
 *
 * @return true if all safety tests pass, false otherwise
 *
 * CRITICAL: This function MUST return true before robot deployment
 * If any test fails, DO NOT operate the robot
 */
bool run_safety_tests(void);

#endif // SAFETY_TEST_H