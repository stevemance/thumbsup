cmake_minimum_required(VERSION 3.13)

# Initialize pico_sdk from submodule
include(pico_sdk_import.cmake)

project(antweight_robot C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Initialize the Raspberry Pi Pico SDK
pico_sdk_init()

# Add Bluepad32 library path
set(BLUEPAD32_PATH ${CMAKE_CURRENT_SOURCE_DIR}/lib/bluepad32)

add_executable(antweight_robot
    src/main.c
    src/bluetooth.c
    src/motor_control.c
    src/drive.c
    src/weapon.c
    src/safety.c
    src/status.c
    src/am32_config.c
)

target_include_directories(antweight_robot PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${BLUEPAD32_PATH}/include
)

# Link libraries
target_link_libraries(antweight_robot
    pico_stdlib
    pico_cyw43_arch_none
    pico_btstack_cyw43
    pico_btstack_classic
    hardware_pwm
    hardware_adc
    hardware_gpio
    hardware_uart
)

# Enable USB output, disable UART output
pico_enable_stdio_usb(antweight_robot 1)
pico_enable_stdio_uart(antweight_robot 0)

# Create map/bin/hex/uf2 files
pico_add_extra_outputs(antweight_robot)

# Add compile definitions
target_compile_definitions(antweight_robot PRIVATE
    PICO_W
    ROBOT_VERSION="1.0.0"
    DEBUG_MODE=1
)

# Add compile options for optimization
target_compile_options(antweight_robot PRIVATE
    -O2
    -Wall
    -Wextra
    -Wno-unused-parameter
)