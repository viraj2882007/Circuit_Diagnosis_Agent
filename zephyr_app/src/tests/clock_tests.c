/**
 * Clock Tests - Clock source and frequency verification
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/clock_control.h>
#include <zephyr/sys_clock.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

/* Test: System clock frequency */
int test_sys_clock(struct diagnostic_context *ctx, struct test_result *result)
{
    uint32_t freq = sys_clock_hw_cycles_per_sec();

    char details[128];
    snprintf(details, sizeof(details), "System clock: %u Hz (%.2f MHz)",
             freq, freq / 1000000.0);

    /* Sanity check: should be reasonable for MCU */
    if (freq > 1000000 && freq < 500000000) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, freq);

    return 0;
}

/* Test: Clock control subsystem */
int test_clock_control(struct diagnostic_context *ctx, struct test_result *result)
{
#if DT_NODE_HAS_STATUS(DT_NODELABEL(rcc), okay) || DT_NODE_HAS_STATUS(DT_NODELABEL(clock), okay)
    const struct device *clk_dev = DEVICE_DT_GET(DT_NODELABEL(clock));
    if (!device_is_ready(clk_dev)) {
        test_result_set_skip(result, "Clock control not available");
        return 0;
    }

    /* Query clock rates for different subsystems */
    struct clock_control_subsys sys_cpu = (struct clock_control_subsys)0;
    struct clock_control_subsys sys_bus = (struct clock_control_subsys)1;

    uint32_t cpu_rate, bus_rate;
    int ret1 = clock_control_get_rate(clk_dev, sys_cpu, &cpu_rate);
    int ret2 = clock_control_get_rate(clk_dev, sys_bus, &bus_rate);

    char details[256];
    snprintf(details, sizeof(details),
             "Clock control: CPU=%u Hz, Bus=%u Hz (ret: %d, %d)",
             cpu_rate, bus_rate, ret1, ret2);

    if (ret1 == 0 && ret2 == 0) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, cpu_rate);
    test_result_add_measurement(result, bus_rate);
#else
    test_result_set_skip(result, "Clock control not available");
#endif

    return 0;
}

/* Test: External crystal (HSE/LSE) */
int test_external_crystal(struct diagnostic_context *ctx, struct test_result *result)
{
    /* This would check if HSE/LSE are enabled and stable */
    /* Implementation depends on specific MCU clock control driver */
    test_result_set_skip(result, "Requires MCU-specific clock driver");
    return 0;
}

/* Test: PLL configuration */
int test_pll_config(struct diagnostic_context *ctx, struct test_result *result)
{
    /* Verify PLL settings match expected values */
    test_result_set_skip(result, "Requires MCU-specific clock driver");
    return 0;
}

/* Clock test suite */
const struct test_case clock_tests[] = {
    {
        .name = "sys_clock",
        .description = "Verify system clock frequency",
        .func = test_sys_clock,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    {
        .name = "clock_control",
        .description = "Query clock control subsystem rates",
        .func = test_clock_control,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    {
        .name = "external_crystal",
        .description = "Check external crystal oscillator status",
        .func = test_external_crystal,
        .timeout_ms = 2000,
        .required_peripherals = 0,
    },
    {
        .name = "pll_config",
        .description = "Verify PLL configuration",
        .func = test_pll_config,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};