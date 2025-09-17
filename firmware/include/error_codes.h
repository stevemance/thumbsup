#ifndef ERROR_CODES_H
#define ERROR_CODES_H

// Standard error codes for ThumbsUp firmware
typedef enum {
    ERROR_SUCCESS = 0,          // Operation succeeded
    ERROR_INVALID_PARAM = -1,   // Invalid parameter passed
    ERROR_NOT_INITIALIZED = -2, // Module not initialized
    ERROR_HARDWARE_FAULT = -3,  // Hardware error detected
    ERROR_TIMEOUT = -4,         // Operation timed out
    ERROR_SAFETY_VIOLATION = -5,// Safety condition violated
    ERROR_OUT_OF_RANGE = -6,    // Value out of acceptable range
    ERROR_COMM_FAILURE = -7,    // Communication failure
    ERROR_BUFFER_OVERFLOW = -8, // Buffer overflow detected
    ERROR_NOT_ARMED = -9,       // Operation requires armed state
    ERROR_FAILSAFE_ACTIVE = -10,// Failsafe is active
    ERROR_LOW_BATTERY = -11,    // Battery too low for operation
    ERROR_UNKNOWN = -99         // Unknown error
} error_code_t;

// Helper macro to check and log errors
#define CHECK_ERROR(result) do { \
    error_code_t _err = (result); \
    if (_err != ERROR_SUCCESS) { \
        DEBUG_PRINT("Error %d at %s:%d\n", _err, __FILE__, __LINE__); \
        return _err; \
    } \
} while(0)

// Helper macro for safety-critical errors
#define SAFETY_CHECK(condition, error) do { \
    if (!(condition)) { \
        DEBUG_PRINT("SAFETY ERROR: %s at %s:%d\n", #condition, __FILE__, __LINE__); \
        return (error); \
    } \
} while(0)

#endif // ERROR_CODES_H