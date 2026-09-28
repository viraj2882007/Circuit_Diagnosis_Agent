/**
 * Test Framework Implementation
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/crc.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#define MAX_RESULTS 128

static struct test_result result_pool[MAX_RESULTS];

int diagnostic_init(struct diagnostic_context *ctx,
                    const struct device *uart_dev,
                    uint8_t *buffer, size_t buffer_size)
{
    if (!ctx || !uart_dev || !buffer || buffer_size < 256) {
        return -EINVAL;
    }

    memset(ctx, 0, sizeof(*ctx));
    ctx->uart_dev = uart_dev;
    ctx->report_buffer = buffer;
    ctx->buffer_size = buffer_size;
    ctx->results = result_pool;
    ctx->result_capacity = MAX_RESULTS;
    ctx->start_time = k_uptime_get_32();

    /* Configure UART for reporting */
    struct uart_config uart_cfg = {
        .baudrate = 115200,
        .parity = UART_CFG_PARITY_NONE,
        .stop_bits = UART_CFG_STOP_BITS_1,
        .data_bits = UART_CFG_DATA_BITS_8,
        .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,
    };
    uart_configure(uart_dev, &uart_cfg);

    return 0;
}

void diagnostic_deinit(struct diagnostic_context *ctx)
{
    if (ctx) {
        memset(ctx, 0, sizeof(*ctx));
    }
}

uint32_t diagnostic_get_time_ms(void)
{
    return k_uptime_get_32();
}

void diagnostic_delay_ms(uint32_t ms)
{
    k_msleep(ms);
}

void test_result_init(struct test_result *result, const char *name)
{
    memset(result, 0, sizeof(*result));
    strncpy(result->name, name, sizeof(result->name) - 1);
    result->timestamp = diagnostic_get_time_ms();
}

void test_result_set_pass(struct test_result *result, const char *details)
{
    result->status = TEST_PASS;
    if (details) {
        strncpy(result->details, details, sizeof(result->details) - 1);
    }
    result->duration_ms = diagnostic_get_time_ms() - result->timestamp;
}

void test_result_set_fail(struct test_result *result, const char *details)
{
    result->status = TEST_FAIL;
    if (details) {
        strncpy(result->details, details, sizeof(result->details) - 1);
    }
    result->duration_ms = diagnostic_get_time_ms() - result->timestamp;
}

void test_result_set_skip(struct test_result *result, const char *details)
{
    result->status = TEST_SKIP;
    if (details) {
        strncpy(result->details, details, sizeof(result->details) - 1);
    }
    result->duration_ms = diagnostic_get_time_ms() - result->timestamp;
}

void test_result_add_measurement(struct test_result *result, uint32_t value)
{
    if (result->measurement_count < 8) {
        result->measurements[result->measurement_count++] = value;
    }
}

int diagnostic_run_suite(struct diagnostic_context *ctx,
                         const struct test_suite *suite)
{
    if (!ctx || !suite || !suite->tests) {
        return -EINVAL;
    }

    ctx->suite_start_time = diagnostic_get_time_ms();
    int passed = 0, failed = 0, skipped = 0;

    for (int i = 0; i < suite->test_count; i++) {
        const struct test_case *test = &suite->tests[i];
        struct test_result *result = &ctx->results[ctx->result_count];

        test_result_init(result, test->name);

        int ret = test->func(ctx, result);
        if (ret < 0) {
            test_result_set_fail(result, "Test function returned error");
            failed++;
        }

        /* Store result */
        ctx->result_count++;

        /* Send progress report */
        diagnostic_send_test_result(ctx, result);

        if (result->status == TEST_PASS) passed++;
        else if (result->status == TEST_FAIL) failed++;
        else skipped++;
    }

    /* Send suite summary */
    diagnostic_send_suite_summary(ctx, suite->name, passed, failed, skipped);

    if (suite->required && failed > 0) {
        return -EIO;
    }

    return 0;
}

int diagnostic_run_single_test(struct diagnostic_context *ctx,
                               const char *test_name,
                               struct test_result *result)
{
    if (!ctx || !test_name || !result) {
        return -EINVAL;
    }

    /* Find test in suites */
    extern const struct test_suite basic_tests[];
    extern const struct test_suite gpio_tests[];
    extern const struct test_suite analog_tests[];
    extern const struct test_suite communication_tests[];
    extern const struct test_suite timing_tests[];
    extern const struct test_suite memory_tests[];
    extern const struct test_suite clock_tests[];

    const struct test_suite *suites[] = {
        basic_tests, gpio_tests, analog_tests,
        communication_tests, timing_tests, memory_tests, clock_tests
    };

    for (size_t s = 0; s < sizeof(suites)/sizeof(suites[0]); s++) {
        for (int j = 0; suites[s][j].name != NULL; j++) {
            if (strcmp(suites[s][j].name, test_name) == 0) {
                test_result_init(result, test_name);
                return suites[s][j].func(ctx, result);
            }
        }
    }

    return -ENOENT;
}

void diagnostic_set_device_id(struct diagnostic_context *ctx,
                              const uint8_t *id, size_t len)
{
    if (ctx && id && len <= sizeof(ctx->device_id)) {
        memcpy(ctx->device_id, id, len);
        ctx->device_id_len = len;
    }
}

/* Reporting functions - implemented in reporting.c */
extern void diagnostic_send_test_result(struct diagnostic_context *ctx,
                                        const struct test_result *result);
extern void diagnostic_send_suite_summary(struct diagnostic_context *ctx,
                                          const char *suite_name,
                                          int passed, int failed, int skipped);
extern int diagnostic_send_final_report(struct diagnostic_context *ctx);
extern void diagnostic_send_device_info(struct diagnostic_context *ctx);