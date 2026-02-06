cmake_minimum_required(VERSION 3.25)

set(PICO_BOARD pico_w)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(thumbsup_controller_emulator C CXX ASM)

pico_sdk_init()

add_executable(thumbsup_controller_emulator
    src/main.c
)

target_include_directories(thumbsup_controller_emulator PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/include
)

target_link_libraries(thumbsup_controller_emulator
    pico_stdlib
    pico_cyw43_arch_none
    pico_btstack_classic
    pico_btstack_cyw43
)

target_compile_definitions(thumbsup_controller_emulator PRIVATE
    PICO_STDIO_USB_CONNECTION_WITHOUT_DTR=1
    PICO_STDIO_USB_STDOUT_TIMEOUT_US=0
)

pico_enable_stdio_usb(thumbsup_controller_emulator 1)
pico_enable_stdio_uart(thumbsup_controller_emulator 0)

pico_add_extra_outputs(thumbsup_controller_emulator)
