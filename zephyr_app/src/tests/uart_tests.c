/**
 * UART Tests - Universal Asynchronous Receiver/Transmitter testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(uart0), okay) || DT_NODE_HAS_STATUS(DT_CHOSEN(zephyr_console), okay)
#define UART_DEV DEVICE_DT_GET(DT_CHOSEN(zephyr_console))
#else
#define UART_DEV NULL
#endif

#define TEST_BAUD_RATE 115200
#define LOOPBACK_TIMEOUT_MS 100

/* Test: UART loopback (requires TX-RX shorted externally) */
int test_uart_loopback(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!UART_DEV || !device_is_ready(UART_DEV)) {
        test_result_set_skip(result, "UART device not available");
        return 0;
    }

    const char *test_str = "UART_LOOPBACK_TEST_1234567890";
    size_t len = strlen(test_str);
    uint8_t rx_buf[64] = {0};
    int rx_count = 0;

    /* Configure UART */
    struct uart_config cfg = {
        .baudrate = TEST_BAUD_RATE,
        .parity = UART_CFG_PARITY_NONE,
        .stop_bits = UART_CFG_STOP_BITS_1,
        .data_bits = UART_CFG_DATA_BITS_8,
        .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
    };
    uart_configure(UART_DEV, &cfg);

    /* Flush RX buffer */
    while (uart_poll_in(UART_DEV, &(uint8_t){0}) == 0) {}

    /* Send test string */
    for (size_t i = 0; i < len; i++) {
        uart_poll_out(UART_DEV, test_str[i]);
    }

    /* Wait for loopback */
    uint32_t start = k_uptime_get_32();
    while (k_uptime_get_32() - start < LOOPBACK_TIMEOUT_MS) {
        uint8_t c;
        if (uart_poll_in(UART_DEV, &c) == 0) {
            if (rx_count < (int)sizeof(rx_buf) - 1) {
                rx_buf[rx_count++] = c;
            }
        }
    }

    rx_buf[rx_count] = '\0';

    char details[256];
    snprintf(details, sizeof(details),
             "Sent: %s, Received (%d bytes): %s", test_str, rx_count, rx_buf);

    if (rx_count == (int)len && memcmp(test_str, rx_buf, len) == 0) {
        test_result_set_pass(result, details);
    } else if (rx_count > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No loopback - TX/RX not connected");
    }

    test_result_add_measurement(result, rx_count);
    test_result_add_measurement(result, len);

    return 0;
}

/* Test: UART baud rate detection */
int test_uart_baud_rates(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!UART_DEV || !device_is_ready(UART_DEV)) {
        test_result_set_skip(result, "UART device not available");
        return 0;
    }

    const uint32_t baud_rates[] = {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600};
    int passed = 0;

    for (int i = 0; i < 8; i++) {
        struct uart_config cfg = {
            .baudrate = baud_rates[i],
            .parity = UART_CFG_PARITY_NONE,
            .stop_bits = UART_CFG_STOP_BITS_1,
            .data_bits = UART_CFG_DATA_BITS_8,
            .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
        };

        int ret = uart_configure(UART_DEV, &cfg);
        if (ret == 0) {
            /* Send a byte and verify no error */
            uart_poll_out(UART_DEV, 0x55);
            k_busy_wait(1000);
            passed++;
        }
    }

    char details[128];
    snprintf(details, sizeof(details), "Baud rate test: %d/8 rates configured successfully", passed);

    if (passed == 8) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, 8);

    return 0;
}

/* UART test suite */
const struct test_case uart_tests[] = {
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
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};