/**
 * SPI Tests - Serial Peripheral Interface testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/spi.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(spi0), okay) || DT_NODE_HAS_STATUS(DT_NODELABEL(spi1), okay)
#define SPI_DEV DEVICE_DT_GET(DT_NODELABEL(spi0))
#else
#define SPI_DEV NULL
#endif

/* SPI loopback test pattern */
static const uint8_t spi_tx_pattern[] = {0x00, 0xFF, 0xAA, 0x55, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80};
static uint8_t spi_rx_buffer[sizeof(spi_tx_pattern)];

/* Test: SPI loopback (requires MISO-MOSI shorted) */
int test_spi_loopback(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!SPI_DEV || !device_is_ready(SPI_DEV)) {
        test_result_set_skip(result, "SPI device not available");
        return 0;
    }

    struct spi_config spi_cfg = {
        .operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_MODE_CPOL | SPI_MODE_CPHA,
        .frequency = 1000000,  /* 1 MHz */
        .slave = 0,
    };

    struct spi_buf tx_buf = {
        .buf = (void *)spi_tx_pattern,
        .len = sizeof(spi_tx_pattern),
    };
    struct spi_buf_set tx_bufs = {.buffers = &tx_buf, .count = 1};

    struct spi_buf rx_buf = {
        .buf = spi_rx_buffer,
        .len = sizeof(spi_rx_buffer),
    };
    struct spi_buf_set rx_bufs = {.buffers = &rx_buf, .count = 1};

    int ret = spi_transceive(SPI_DEV, &spi_cfg, &tx_bufs, &rx_bufs);
    if (ret < 0) {
        test_result_set_fail(result, "SPI transceive failed");
        return 0;
    }

    /* Check received data */
    int errors = 0;
    for (size_t i = 0; i < sizeof(spi_tx_pattern); i++) {
        if (spi_rx_buffer[i] != spi_tx_pattern[i]) {
            errors++;
        }
    }

    char details[256];
    snprintf(details, sizeof(details),
             "SPI loopback: %zu bytes, %d errors. TX: %02X %02X %02X... RX: %02X %02X %02X...",
             sizeof(spi_tx_pattern), errors,
             spi_tx_pattern[0], spi_tx_pattern[1], spi_tx_pattern[2],
             spi_rx_buffer[0], spi_rx_buffer[1], spi_rx_buffer[2]);

    if (errors == 0) {
        test_result_set_pass(result, details);
    } else if (errors < (int)sizeof(spi_tx_pattern)) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No loopback - MISO/MOSI not connected");
    }

    test_result_add_measurement(result, errors);
    test_result_add_measurement(result, sizeof(spi_tx_pattern));

    return 0;
}

/* Test: SPI frequency sweep */
int test_spi_frequency(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!SPI_DEV || !device_is_ready(SPI_DEV)) {
        test_result_set_skip(result, "SPI device not available");
        return 0;
    }

    const uint32_t frequencies[] = {100000, 500000, 1000000, 2000000, 4000000, 8000000};
    int passed = 0;

    for (int i = 0; i < 6; i++) {
        struct spi_config spi_cfg = {
            .operation = SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_MODE_CPOL | SPI_MODE_CPHA,
            .frequency = frequencies[i],
            .slave = 0,
        };

        struct spi_buf tx_buf = {.buf = (void *)spi_tx_pattern, .len = 4};
        struct spi_buf_set tx_bufs = {.buffers = &tx_buf, .count = 1};

        int ret = spi_write(SPI_DEV, &spi_cfg, &tx_bufs);
        if (ret == 0) {
            passed++;
        }
    }

    char details[128];
    snprintf(details, sizeof(details), "SPI frequency test: %d/6 frequencies successful", passed);

    if (passed == 6) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, 6);

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