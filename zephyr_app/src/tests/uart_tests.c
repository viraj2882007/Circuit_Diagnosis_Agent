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

/* UART0/console is shared with diagnostic reporting. Generic loopback is opt-in only. */
int test_uart_loopback(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "UART loopback disabled by default: requires a separate board-profile UART and verified TX-RX loopback.");
    return 0;
}

/* Baud-rate testing must not reconfigure the serial console used for reporting. */
int test_uart_baud_rates(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "Baud-rate sweep disabled on the diagnostic console; add a separate UART fixture.");
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