/**
 * SPI Tests - Serial Peripheral Interface testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/spi.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

/* Generic SPI tests remain skipped until a safe, board-specific bus profile exists. */
int test_spi_loopback(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "SPI loopback requires a board-specific pin route and confirmed device isolation.");
    return 0;
}

int test_spi_frequency(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "SPI frequency requires a board-specific timing capture; no measurement was made.");
    return 0;
}

/* SPI test suite */
const struct test_case spi_tests[] = {
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
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};