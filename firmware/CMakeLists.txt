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

# USB identification for serial tools and picotool.
set(THUMBSUP_USB_MANUFACTURER "ThumbsUp" CACHE STRING "USB manufacturer string")
set(THUMBSUP_USB_PRODUCT "ThumbsUp HITL Robot" CACHE STRING "USB product string")

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
    src/hitl_overrides.c
    src/hitl_console.c
    src/safety_test.c
    src/integration_test.c
    src/serial_gamepad.c
)

# Competition mode (Bluetooth) - diagnostic mode removed
message(STATUS "Building for COMPETITION MODE (Bluetooth)")
add_executable(thumbsup
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

add_executable(thumbsup_hitl
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

add_executable(thumbsup_debug
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

add_executable(thumbsup_integration
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

add_executable(thumbsup_serial
    ${CORE_SOURCES}
    src/bluetooth_platform.c
    src/test_mode.c
)

# Generate PIO headers
pico_generate_pio_header(thumbsup ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)
pico_generate_pio_header(thumbsup_hitl ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup_hitl ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)
pico_generate_pio_header(thumbsup_debug ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup_debug ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)
pico_generate_pio_header(thumbsup_integration ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup_integration ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)
pico_generate_pio_header(thumbsup_serial ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio)
pico_generate_pio_header(thumbsup_serial ${CMAKE_CURRENT_LIST_DIR}/src/dshot.pio)

# Include directories (competition mode - Bluetooth/Bluepad32)
target_include_directories(thumbsup PRIVATE
    include
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)
target_include_directories(thumbsup_hitl PRIVATE
    include
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)
target_include_directories(thumbsup_debug PRIVATE
    include
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)
target_include_directories(thumbsup_integration PRIVATE
    include
    ${BLUEPAD32_ROOT}/src/components/bluepad32/include)
target_include_directories(thumbsup_serial PRIVATE
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

target_link_libraries(thumbsup_hitl PUBLIC
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

target_link_libraries(thumbsup_debug PUBLIC
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

pico_enable_stdio_usb(thumbsup_integration 1)
pico_enable_stdio_uart(thumbsup_integration 0)

target_link_libraries(thumbsup_integration PUBLIC
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

target_compile_definitions(thumbsup_integration PRIVATE
    INTEGRATION_TEST_AUTO=1
    AM32_ONEWIRE=1
    PICO_STDIO_USB_CONNECTION_WITHOUT_DTR=1
    PICO_STDIO_USB_ENABLE_TINYUSB_INIT=1
    PICO_STDIO_USB_ENABLE_IRQ_BACKGROUND_TASK=1
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=0
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    USBD_MANUFACTURER=\"${THUMBSUP_USB_MANUFACTURER}\"
    USBD_PRODUCT=\"${THUMBSUP_USB_PRODUCT}\")

pico_enable_stdio_usb(thumbsup_serial 1)
pico_enable_stdio_uart(thumbsup_serial 0)

target_link_libraries(thumbsup_serial PUBLIC
    pico_stdlib
    hardware_pwm
    hardware_adc
    hardware_gpio
    hardware_uart
    hardware_watchdog
    hardware_pio
    hardware_dma
    hardware_flash
    hardware_sync
)

target_compile_definitions(thumbsup_serial PRIVATE
    SERIAL_GAMEPAD=1
    PICO_STDIO_USB_CONNECTION_WITHOUT_DTR=1
    PICO_STDIO_USB_ENABLE_TINYUSB_INIT=1
    PICO_STDIO_USB_ENABLE_IRQ_BACKGROUND_TASK=1
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    AM32_ONEWIRE=1
    USBD_MANUFACTURER=\"${THUMBSUP_USB_MANUFACTURER}\"
    USBD_PRODUCT=\"${THUMBSUP_USB_PRODUCT}\"
)

target_compile_definitions(thumbsup PRIVATE
    AM32_ONEWIRE=1
    PICO_STDIO_USB_ENABLE_TINYUSB_INIT=1
    PICO_STDIO_USB_ENABLE_IRQ_BACKGROUND_TASK=1
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    USBD_MANUFACTURER=\"${THUMBSUP_USB_MANUFACTURER}\"
    USBD_PRODUCT=\"${THUMBSUP_USB_PRODUCT}\"
)

pico_enable_stdio_usb(thumbsup 1)
pico_enable_stdio_uart(thumbsup 0)

target_compile_definitions(thumbsup_debug PRIVATE
    HITL_CONSOLE=1
    AM32_ONEWIRE=1
    PICO_STDIO_USB_CONNECTION_WITHOUT_DTR=1
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=0
    CFG_TUD_CDC_TX_BUFSIZE=512
    PICO_STDIO_USB_ENABLE_TINYUSB_INIT=1
    PICO_STDIO_USB_ENABLE_IRQ_BACKGROUND_TASK=1
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    USBD_MANUFACTURER=\"${THUMBSUP_USB_MANUFACTURER}\"
    USBD_PRODUCT=\"${THUMBSUP_USB_PRODUCT}\"
)

target_compile_definitions(thumbsup_hitl PRIVATE
    HITL_CONSOLE=1
    HITL_NO_SCAN=1
    AM32_ONEWIRE=1
    PICO_STDIO_USB_CONNECTION_WITHOUT_DTR=1
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=0
    CFG_TUD_CDC_TX_BUFSIZE=512
    PICO_STDIO_USB_ENABLE_TINYUSB_INIT=1
    PICO_STDIO_USB_ENABLE_IRQ_BACKGROUND_TASK=1
    PICO_STDIO_USB_ENABLE_RESET_VIA_VENDOR_INTERFACE=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_BOOTSEL=1
    PICO_STDIO_USB_RESET_INTERFACE_SUPPORT_RESET_TO_FLASH_BOOT=1
    USBD_MANUFACTURER=\"${THUMBSUP_USB_MANUFACTURER}\"
    USBD_PRODUCT=\"${THUMBSUP_USB_PRODUCT}\"
)

pico_enable_stdio_usb(thumbsup_hitl 1)
pico_enable_stdio_uart(thumbsup_hitl 0)

# Competition-debug build: full competition stack + serial HITL console output.
pico_enable_stdio_usb(thumbsup_debug 1)
pico_enable_stdio_uart(thumbsup_debug 0)

# create map/bin/hex/uf2 file in addition to ELF.
pico_add_extra_outputs(thumbsup)
pico_add_extra_outputs(thumbsup_hitl)
pico_add_extra_outputs(thumbsup_debug)
pico_add_extra_outputs(thumbsup_integration)
pico_add_extra_outputs(thumbsup_serial)
