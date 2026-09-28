/**
 * Timer Tests - Timer/PWM/Counter testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/counter.h>
#include <zephyr/drivers/pwm.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(timer0), okay) || DT_NODE_HAS_STATUS(DT_NODELABEL(pwm0), okay)
#define PWM_DEV DEVICE_DT_GET(DT_NODELABEL(pwm0))
#define COUNTER_DEV DEVICE_DT_GET(DT_NODELABEL(timer0))
#else
#define PWM_DEV NULL
#define COUNTER_DEV NULL
#endif

/* Test: PWM output */
int test_pwm_output(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!PWM_DEV || !device_is_ready(PWM_DEV)) {
        test_result_set_skip(result, "PWM device not available");
        return 0;
    }

    const uint32_t period_ns = 1000000;  /* 1ms period = 1kHz */
    const uint32_t duty_cycles[] = {0, period_ns/4, period_ns/2, 3*period_ns/4, period_ns};
    int passed = 0;

    for (int ch = 0; ch < 4; ch++) {
        for (int i = 0; i < 5; i++) {
            int ret = pwm_set(PWM_DEV, ch, period_ns, duty_cycles[i], PWM_POLARITY_NORMAL);
            if (ret == 0) {
                passed++;
            }
            k_busy_wait(1000);
        }
        /* Disable channel */
        pwm_set(PWM_DEV, ch, period_ns, 0, PWM_POLARITY_NORMAL);
    }

    char details[128];
    snprintf(details, sizeof(details), "PWM output test: %d/20 channel/duty combinations successful", passed);

    if (passed == 20) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, 20);

    return 0;
}

/* Test: Timer/counter basic */
int test_timer_count(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!COUNTER_DEV || !device_is_ready(COUNTER_DEV)) {
        test_result_set_skip(result, "Counter device not available");
        return 0;
    }

    struct counter_top_cfg top_cfg = {
        .ticks = 1000000,  /* 1 second at 1MHz */
        .flags = COUNTER_TOP_CFG_DONT_RESET,
    };

    int ret = counter_set_top_value(COUNTER_DEV, &top_cfg);
    if (ret < 0) {
        test_result_set_fail(result, "Failed to set counter top value");
        return 0;
    }

    ret = counter_start(COUNTER_DEV);
    if (ret < 0) {
        test_result_set_fail(result, "Failed to start counter");
        return 0;
    }

    k_msleep(100);

    uint32_t count = counter_get_value(COUNTER_DEV);
    counter_stop(COUNTER_DEV);

    char details[128];
    snprintf(details, sizeof(details), "Timer count after 100ms: %u", count);

    /* Expect roughly 100000 counts at 1MHz */
    if (count > 50000 && count < 150000) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, count);

    return 0;
}

/* Test: Input capture (requires external signal) */
int test_input_capture(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(result, "Requires external signal generator");
    return 0;
}

/* Test: RTC */
int test_rtc(struct diagnostic_context *ctx, struct test_result *result)
{
#if DT_NODE_HAS_STATUS(DT_NODELABEL(rtc), okay)
    const struct device *rtc_dev = DEVICE_DT_GET(DT_NODELABEL(rtc));
    if (!device_is_ready(rtc_dev)) {
        test_result_set_skip(result, "RTC not available");
        return 0;
    }

    struct counter_alarm_cfg alarm = {
        .flags = 0,
        .ticks = 1000,  /* 1 second */
    };

    int ret = counter_set_channel_alarm(rtc_dev, 0, &alarm);
    if (ret < 0) {
        test_result_set_fail(result, "RTC alarm set failed");
        return 0;
    }

    k_msleep(1100);

    uint32_t val = counter_get_value(rtc_dev);
    counter_stop(rtc_dev);

    char details[128];
    snprintf(details, sizeof(details), "RTC value after alarm: %u", val);

    if (val > 900) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, val);
#else
    test_result_set_skip(result, "RTC not available");
#endif

    return 0;
}

/* Timer test suite */
const struct test_case timer_tests[] = {
    {
        .name = "pwm_output",
        .description = "Test PWM output on multiple channels and duty cycles",
        .func = test_pwm_output,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_PWM,
    },
    {
        .name = "timer_count",
        .description = "Basic timer/counter functionality test",
        .func = test_timer_count,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_TIMER,
    },
    {
        .name = "input_capture",
        .description = "Timer input capture test (requires external signal)",
        .func = test_input_capture,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_TIMER,
    },
    {
        .name = "rtc_test",
        .description = "Real-time counter test",
        .func = test_rtc,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_TIMER,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};