/**
 * I2C Tests - Inter-Integrated Circuit testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

/* I2C bus selection is board-specific. Do not probe arbitrary attached devices
 * during boot until a user-selected, voltage-verified bus profile exists.
 */
int test_i2c_scan(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "I2C scan requires an explicitly selected, voltage-verified board bus profile.");
    return 0;
}

int test_i2c_eeprom(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "I2C EEPROM writes are disabled without an identified device, reserved test region, and recovery plan.");
    return 0;
}

int test_i2c_speed(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "I2C speed modes need a board-specific bus and measurement fixture.");
    return 0;
}

/* I2C test suite */
const struct test_case i2c_tests[] = {
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