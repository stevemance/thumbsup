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
