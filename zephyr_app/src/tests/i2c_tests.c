/**
 * I2C Tests - Inter-Integrated Circuit testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(i2c0), okay)
#define I2C_DEV DEVICE_DT_GET(DT_NODELABEL(i2c0))
#elif DT_NODE_HAS_STATUS(DT_NODELABEL(i2c1), okay)
#define I2C_DEV DEVICE_DT_GET(DT_NODELABEL(i2c1))
#else
#define I2C_DEV NULL
#endif

#define I2C_TEST_ADDR 0x50  /* Typical EEPROM address */

/* Test: I2C bus scan */
int test_i2c_scan(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!I2C_DEV || !device_is_ready(I2C_DEV)) {
        test_result_set_skip(result, "I2C device not available");
        return 0;
    }

    uint8_t found_devices[128] = {0};
    int device_count = 0;

    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        /* Try to write 0 bytes to address */
        int ret = i2c_write(I2C_DEV, NULL, 0, addr);
        if (ret == 0) {
            found_devices[addr] = 1;
            device_count++;
        }
    }

    char details[256];
    size_t used = 0;
    int written = snprintf(details, sizeof(details), "I2C scan found %d ACK response(s):", device_count);
    if (written < 0) {
        test_result_set_fail(result, "Could not format I2C scan result.");
        return 0;
    }
    used = (size_t)written < sizeof(details) ? (size_t)written : sizeof(details) - 1U;

    for (int addr = 0x08; addr < 0x78 && used < sizeof(details) - 1U; addr++) {
        if (found_devices[addr]) {
            written = snprintf(details + used, sizeof(details) - used, " 0x%02X", addr);
            if (written < 0) break;
            if ((size_t)written >= sizeof(details) - used) {
                used = sizeof(details) - 1U;
                break;
            }
            used += (size_t)written;
        }
    }

    if (device_count > 0) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_skip(result, "No I2C address ACKed; no device presence was established, so this is not a board failure.");
    }

    test_result_add_measurement(result, device_count);

    return 0;
}

/* Writing to a guessed EEPROM address could modify user data; disabled by default. */
int test_i2c_eeprom(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "I2C EEPROM writes are disabled without an identified device, reserved test region, and recovery plan.");
    return 0;
}

/* No controller timing is measured by the old placeholder loop; do not claim PASS. */
int test_i2c_speed(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "I2C speed modes are not measured; add a board-specific timing fixture before validating speed.");
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