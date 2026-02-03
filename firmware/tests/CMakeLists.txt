cmake_minimum_required(VERSION 3.13)

# One-off bench tests (no Bluepad32 dependency)
set(PICO_BOARD "pico_w")

# initialize the SDK based on PICO_SDK_PATH
include(../pico_sdk_import.cmake)

project(thumbsup_tests C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# initialize the Raspberry Pi Pico SDK
pico_sdk_init()

get_filename_component(FIRMWARE_DIR ${CMAKE_CURRENT_LIST_DIR}/.. ABSOLUTE)
set(FIRMWARE_SRC_DIR ${FIRMWARE_DIR}/src)
set(TESTS_SRC_DIR ${CMAKE_CURRENT_LIST_DIR}/src)

# --- DShot beep test ---
add_executable(dshot_beep_test
    ${TESTS_SRC_DIR}/dshot_beep_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_beep_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_beep_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_beep_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_beep_test 1)
pico_enable_stdio_uart(dshot_beep_test 0)
pico_add_extra_outputs(dshot_beep_test)

# --- DShot spin test ---
add_executable(dshot_spin_test
    ${TESTS_SRC_DIR}/dshot_spin_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_spin_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_spin_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_spin_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_spin_test 1)
pico_enable_stdio_uart(dshot_spin_test 0)
pico_add_extra_outputs(dshot_spin_test)

# --- DShot telemetry spin test ---
add_executable(dshot_telemetry_spin_test
    ${TESTS_SRC_DIR}/dshot_telemetry_spin_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_telemetry_spin_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_telemetry_spin_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_telemetry_spin_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_telemetry_spin_test 1)
pico_enable_stdio_uart(dshot_telemetry_spin_test 0)
pico_add_extra_outputs(dshot_telemetry_spin_test)

# --- DShot telemetry hold test ---
add_executable(dshot_telemetry_hold_test
    ${TESTS_SRC_DIR}/dshot_telemetry_hold_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_telemetry_hold_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_telemetry_hold_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_telemetry_hold_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_telemetry_hold_test 1)
pico_enable_stdio_uart(dshot_telemetry_hold_test 0)
pico_add_extra_outputs(dshot_telemetry_hold_test)

# --- DShot telemetry single RPM test ---
add_executable(dshot_telemetry_single_rpm_test
    ${TESTS_SRC_DIR}/dshot_telemetry_single_rpm_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_telemetry_single_rpm_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_telemetry_single_rpm_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_telemetry_single_rpm_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_telemetry_single_rpm_test 1)
pico_enable_stdio_uart(dshot_telemetry_single_rpm_test 0)
pico_add_extra_outputs(dshot_telemetry_single_rpm_test)

# --- DShot telemetry calibration test ---
add_executable(dshot_telemetry_calibration_test
    ${TESTS_SRC_DIR}/dshot_telemetry_calibration_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_telemetry_calibration_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_telemetry_calibration_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_telemetry_calibration_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_telemetry_calibration_test 1)
pico_enable_stdio_uart(dshot_telemetry_calibration_test 0)
pico_add_extra_outputs(dshot_telemetry_calibration_test)

# --- DShot single RPM test ---
add_executable(dshot_single_rpm_test
    ${TESTS_SRC_DIR}/dshot_single_rpm_test.c
    ${FIRMWARE_SRC_DIR}/dshot.c
)

pico_generate_pio_header(dshot_single_rpm_test ${FIRMWARE_SRC_DIR}/dshot.pio)

target_include_directories(dshot_single_rpm_test PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(dshot_single_rpm_test
    pico_stdlib
    pico_sync
    hardware_clocks
    hardware_dma
    hardware_gpio
    hardware_irq
    hardware_pio
)

pico_enable_stdio_usb(dshot_single_rpm_test 1)
pico_enable_stdio_uart(dshot_single_rpm_test 0)
pico_add_extra_outputs(dshot_single_rpm_test)

# --- AM32 one-wire config probe ---
add_executable(am32_onewire_probe
    ${TESTS_SRC_DIR}/am32_onewire_probe.c
    ${FIRMWARE_SRC_DIR}/am32_config.c
)

target_compile_definitions(am32_onewire_probe PRIVATE AM32_ONEWIRE=1)

target_include_directories(am32_onewire_probe PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(am32_onewire_probe
    pico_stdlib
    hardware_gpio
    hardware_pwm
    hardware_sync
    hardware_timer
    hardware_uart
    hardware_watchdog
)

pico_enable_stdio_usb(am32_onewire_probe 1)
pico_enable_stdio_uart(am32_onewire_probe 0)
pico_add_extra_outputs(am32_onewire_probe)

# --- AM32 bootloader EEPROM probe ---
add_executable(am32_bootloader_probe
    ${TESTS_SRC_DIR}/am32_bootloader_probe.c
    ${FIRMWARE_SRC_DIR}/am32_bootloader.c
)

pico_generate_pio_header(am32_bootloader_probe ${FIRMWARE_SRC_DIR}/pio_uart.pio)

target_include_directories(am32_bootloader_probe PRIVATE ${FIRMWARE_DIR}/include)

target_link_libraries(am32_bootloader_probe
    pico_stdlib
    hardware_clocks
    hardware_gpio
    hardware_pio
)

pico_enable_stdio_usb(am32_bootloader_probe 1)
pico_enable_stdio_uart(am32_bootloader_probe 0)
pico_add_extra_outputs(am32_bootloader_probe)
