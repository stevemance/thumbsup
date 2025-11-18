cmake_minimum_required(VERSION 3.13)

# Competition mode only (Bluetooth) - diagnostic mode removed

# PICO_BOARD should be set to 'pico_w', or not set at all.
if(DEFINED PICO_BOARD AND NOT ${PICO_BOARD} STREQUAL "pico_w")
    message(FATAL_ERROR "PICO_BOARD must be set to 'pico_w' or not set at all")
else()
    set(PICO_BOARD "pico_w")
endif()

# Bluepad32 configuration (required for competition mode)
if(DEFINED ENV{BLUEPAD32_ROOT})
    set(BLUEPAD32_ROOT $ENV{BLUEPAD32_ROOT})
else()
    message(FATAL_ERROR "BLUEPAD32_ROOT environment variable is not set")
endif()

# BTstack configuration (from Bluepad32 with custom controller patches)
set(BTSTACK_ROOT ${BLUEPAD32_ROOT}/external/btstack)
set(PICO_BTSTACK_PATH ${BTSTACK_ROOT})

# initialize the SDK based on PICO_SDK_PATH
# note: this must happen before project()
include(pico_sdk_import.cmake)

project(thumbsup C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# initialize the Raspberry Pi Pico SDK
pico_sdk_init()

# Core source files for both modes
set(CORE_SOURCES
    src/main.c
    src/motor_control.c
    src/drive.c
    src/weapon.c
    src/safety.c
    src/status.c
    src/ws2812.c
    src/trim_mode.c
    src/calibration_mode.c
    src/motor_linearization.c
    src/am32_config.c
    src/dshot.c
    src/safety_test.c
)

# Competition mode (Bluetooth) - diagnostic mode removed
message(STATUS "Building for COMPETITION MODE (Bluetooth)")
add_executable(thumbsup
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

# Generate PIO headers
pico_generate_pio_header(thumbsup ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)

# Include directories (competition mode - Bluetooth/Bluepad32)
target_include_directories(thumbsup PRIVATE
    include
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)

# Needed for btstack_config.h / sdkconfig.h
# so that libbluepad32 can include them
include_directories(thumbsup include)

# Needed when using BTstack from our branch
include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/encoder/include)
include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/decoder/include)

# Link libraries (competition mode - Bluetooth)
target_link_libraries(thumbsup PUBLIC
    pico_stdlib
    pico_cyw43_arch_none  # Bluetooth support
    pico_btstack_classic
    pico_btstack_cyw43
    hardware_pwm
    hardware_adc
    hardware_gpio
    hardware_uart
    hardware_watchdog
    hardware_pio
    hardware_dma
    hardware_flash
    hardware_sync
    bluepad32
)
add_subdirectory(${BLUEPAD32_ROOT}/src/components/bluepad32 libbluepad32)

pico_enable_stdio_usb(thumbsup 1)
pico_enable_stdio_uart(thumbsup 0)

# create map/bin/hex/uf2 file in addition to ELF.
pico_add_extra_outputs(thumbsup)