/**
 * Timing Tests - Combined timer/PWM test suite
 */

#include "test_framework.h"

/* External test suite declarations */
extern const struct test_case timer_tests[];

/* Combined timing test suite */
const struct test_case timing_tests[] = {
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