cmake_minimum_required(VERSION 3.13)

# Build mode option - DIAGNOSTIC_MODE=ON for WiFi diagnostic, OFF for Bluetooth competition
option(DIAGNOSTIC_MODE "Build for diagnostic mode (WiFi) instead of competition mode (Bluetooth)" OFF)

# PICO_BOARD should be set to 'pico_w', or not set at all.
if(DEFINED PICO_BOARD AND NOT ${PICO_BOARD} STREQUAL "pico_w")
    message(FATAL_ERROR "PICO_BOARD must be set to 'pico_w' or not set at all")
else()
    set(PICO_BOARD "pico_w")
endif()

# Only need Bluepad32 for competition mode
if(NOT DIAGNOSTIC_MODE)
    if(DEFINED ENV{BLUEPAD32_ROOT})
        set(BLUEPAD32_ROOT $ENV{BLUEPAD32_ROOT})
    else()
        message(FATAL_ERROR "BLUEPAD32_ROOT environment variable is not set for competition mode")
    endif()
endif()

# BTstack configuration for competition mode
if(NOT DIAGNOSTIC_MODE)
    # To use BTstack from Pico SDK do
    #set(BTSTACK_ROOT ${PICO_SDK_PATH}/lib/btstack)
    # To use it from Bluepad32 (up-to-date, with custom patches for controllers):
    set(BTSTACK_ROOT ${BLUEPAD32_ROOT}/external/btstack)
    set(PICO_BTSTACK_PATH ${BTSTACK_ROOT})
endif()

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
    src/am32_config.c
    src/safety_test.c
)

if(DIAGNOSTIC_MODE)
    message(STATUS "Building for DIAGNOSTIC MODE (WiFi)")
    add_executable(thumbsup
        ${CORE_SOURCES}
        src/diagnostic_mode.c
        src/web_server.c
        src/dhcp_server.c
    )
else()
    message(STATUS "Building for COMPETITION MODE (Bluetooth)")
    add_executable(thumbsup
        ${CORE_SOURCES}
        src/bluetooth_platform.c
        src/test_mode.c
    )
endif()

# Include directories
if(DIAGNOSTIC_MODE)
    target_include_directories(thumbsup PRIVATE
        include
    )
else()
    target_include_directories(thumbsup PRIVATE
        include
        ${BLUEPAD32_ROOT}/src/components/bluepad32/include)

    # Needed for btstack_config.h / sdkconfig.h
    # so that libbluepad32 can include them
    include_directories(thumbsup include)

    # Needed when using BTstack from our branch
    include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/encoder/include)
    include_directories(${BTSTACK_ROOT}/3rd-party/bluedroid/decoder/include)
endif()

# Link libraries based on mode
if(DIAGNOSTIC_MODE)
    target_link_libraries(thumbsup PUBLIC
        pico_stdlib
        pico_cyw43_arch_lwip_poll  # WiFi support
        pico_lwip_http
        hardware_pwm
        hardware_adc
        hardware_gpio
        hardware_uart
        hardware_watchdog
    )
    # Compile definition for diagnostic mode
    target_compile_definitions(thumbsup PRIVATE DIAGNOSTIC_MODE_BUILD=1)
else()
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
        bluepad32
    )
    add_subdirectory(${BLUEPAD32_ROOT}/src/components/bluepad32 libbluepad32)
    # Compile definition for competition mode
    target_compile_definitions(thumbsup PRIVATE DIAGNOSTIC_MODE_BUILD=0)
endif()

pico_enable_stdio_usb(thumbsup 1)
pico_enable_stdio_uart(thumbsup 0)

# create map/bin/hex/uf2 file in addition to ELF.
pico_add_extra_outputs(thumbsup)