#ifndef INTEGRATION_TEST_H
#define INTEGRATION_TEST_H

#include <stdbool.h>
#include <stdint.h>

// Runs the integration test if the user presses the trigger key within the timeout.
// Returns true if the test was executed (caller should halt normal startup).
bool integration_test_run_if_requested(uint32_t timeout_ms);

#endif  // INTEGRATION_TEST_H
