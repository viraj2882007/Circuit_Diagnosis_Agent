/**
 * Communication Tests - Combined UART/SPI/I2C test suite
 */

#include "test_framework.h"

/* External test suite declarations */
extern const struct test_case uart_tests[];
extern const struct test_case spi_tests[];
extern const struct test_case i2c_tests[];

/* Combined communication test suite */
const struct test_case communication_tests[] = {
    /* UART tests */
    {
        .name = "uart_loopback",
        .description = "UART TX-RX loopback test (requires external jumper)",
        .func = test_uart_loopback,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_UART,
    },
    {
        .name = "uart_baud_rates",
        .description = "Test UART configuration at standard baud rates",
        .func = test_uart_baud_rates,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_UART,
    },
    /* SPI tests */
    {
        .name = "spi_loopback",
        .description = "SPI MISO-MOSI loopback test (requires external jumper)",
        .func = test_spi_loopback,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_SPI,
    },
    {
        .name = "spi_frequency",
        .description = "Test SPI at multiple clock frequencies",
        .func = test_spi_frequency,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_SPI,
    },
    /* I2C tests */
    {
        .name = "i2c_scan",
        .description = "Scan I2C bus for connected devices",
        .func = test_i2c_scan,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_I2C,
    },
    {
        .name = "i2c_eeprom",
        .description = "I2C EEPROM read/write test (requires EEPROM at 0x50)",
        .func = test_i2c_eeprom,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_I2C,
    },
    {
        .name = "i2c_speed",
        .description = "Test I2C at different speed modes",
        .func = test_i2c_speed,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_I2C,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};