# MCU Diagnostic Test Firmware - Zephyr Application
# This firmware runs on the target MCU and performs peripheral self-tests

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(mcu_diagnostic_firmware)

# Parse test suites from CMake command line
if(NOT DEFINED DIAGNOSTIC_TEST_SUITES)
    set(DIAGNOSTIC_TEST_SUITES "basic;gpio;adc;dac;uart;spi;i2c;timing;memory;clock")
endif()

# Convert the CMake list into one comma-separated C string.
string(REPLACE ";" "," TEST_SUITES_STR "${DIAGNOSTIC_TEST_SUITES}")
add_compile_definitions(DIAGNOSTIC_TEST_SUITES="${TEST_SUITES_STR}")

# Enable required features
target_sources(app PRIVATE
    src/main.c
    src/tests/test_framework.c
    src/tests/basic_tests.c
    src/tests/gpio_tests.c
    src/tests/adc_tests.c
    src/tests/dac_tests.c
    src/tests/uart_tests.c
    src/tests/spi_tests.c
    src/tests/i2c_tests.c
    src/tests/timer_tests.c
    src/tests/memory_tests.c
    src/tests/clock_tests.c
    src/comm/reporting.c
    src/comm/serial_protocol.c
)

# Include directories
target_include_directories(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/tests
    ${CMAKE_CURRENT_SOURCE_DIR}/src/comm
)

# Compile definitions
target_compile_definitions(app PRIVATE
    DIAGNOSTIC_FIRMWARE_VERSION=1
    CONFIG_DIAGNOSTIC_BUFFER_SIZE=2048
)


# Zephyr's CMake package links enabled kernel/drivers through app; do not
# manually link synthetic driver target names.
