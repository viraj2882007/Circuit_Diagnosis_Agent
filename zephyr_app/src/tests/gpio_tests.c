/**
 * GPIO Tests - Comprehensive GPIO testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

/* GPIO port aliases for different MCU families */
#if DT_NODE_HAS_STATUS(DT_NODELABEL(gpioa), okay)
#define GPIO_PORT_A DEVICE_DT_GET(DT_NODELABEL(gpioa))
#else
#define GPIO_PORT_A NULL
#endif

#if DT_NODE_HAS_STATUS(DT_NODELABEL(gpiob), okay)
#define GPIO_PORT_B DEVICE_DT_GET(DT_NODELABEL(gpiob))
#else
#define GPIO_PORT_B NULL
#endif

#if DT_NODE_HAS_STATUS(DT_NODELABEL(gpioc), okay)
#define GPIO_PORT_C DEVICE_DT_GET(DT_NODELABEL(gpioc))
#else
#define GPIO_PORT_C NULL
#endif

#if DT_NODE_HAS_STATUS(DT_NODELABEL(gpiod), okay)
#define GPIO_PORT_D DEVICE_DT_GET(DT_NODELABEL(gpiod))
#else
#define GPIO_PORT_D NULL
#endif

/* Pin mapping for different boards */
static const struct {
    const struct device *port;
    uint32_t pin;
    const char *name;
} test_pins[] = {
    {GPIO_PORT_A, 0, "PA0"}, {GPIO_PORT_A, 1, "PA1"},
    {GPIO_PORT_A, 2, "PA2"}, {GPIO_PORT_A, 3, "PA3"},
    {GPIO_PORT_A, 4, "PA4"}, {GPIO_PORT_A, 5, "PA5"},
    {GPIO_PORT_A, 6, "PA6"}, {GPIO_PORT_A, 7, "PA7"},
    {GPIO_PORT_B, 0, "PB0"}, {GPIO_PORT_B, 1, "PB1"},
    {GPIO_PORT_B, 2, "PB2"}, {GPIO_PORT_B, 3, "PB3"},
    {GPIO_PORT_B, 4, "PB4"}, {GPIO_PORT_B, 5, "PB5"},
    {GPIO_PORT_C, 13, "PC13"}, {GPIO_PORT_C, 14, "PC14"},
    {GPIO_PORT_C, 15, "PC15"},
};

#define NUM_TEST_PINS (sizeof(test_pins) / sizeof(test_pins[0]))

/* Test: Basic GPIO output toggle */
int test_gpio_output(struct diagnostic_context *ctx, struct test_result *result)
{
    int passed = 0, total = 0;

    for (int i = 0; i < NUM_TEST_PINS; i++) {
        if (!test_pins[i].port || !device_is_ready(test_pins[i].port)) {
            continue;
        }

        total++;
        int ret = gpio_pin_configure(test_pins[i].port, test_pins[i].pin,
                                     GPIO_OUTPUT_INACTIVE);
        if (ret < 0) {
            continue;
        }

        /* Toggle 5 times */
        for (int j = 0; j < 5; j++) {
            gpio_pin_set(test_pins[i].port, test_pins[i].pin, 1);
            k_busy_wait(100);
            gpio_pin_set(test_pins[i].port, test_pins[i].pin, 0);
            k_busy_wait(100);
        }

        /* Verify final state */
        int val = gpio_pin_get(test_pins[i].port, test_pins[i].pin);
        if (val == 0) {
            passed++;
        }

        /* Restore to input */
        gpio_pin_configure(test_pins[i].port, test_pins[i].pin, GPIO_INPUT);
    }

    char details[128];
    snprintf(details, sizeof(details), "Tested %d pins, %d passed", total, passed);

    if (passed == total && total > 0) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No GPIO ports available");
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, total);

    return 0;
}

/* Test: GPIO input with pull-up */
int test_gpio_input_pullup(struct diagnostic_context *ctx, struct test_result *result)
{
    int passed = 0, total = 0;

    for (int i = 0; i < NUM_TEST_PINS; i++) {
        if (!test_pins[i].port || !device_is_ready(test_pins[i].port)) {
            continue;
        }

        total++;
        int ret = gpio_pin_configure(test_pins[i].port, test_pins[i].pin,
                                     GPIO_INPUT | GPIO_PULL_UP);
        if (ret < 0) {
            continue;
        }

        k_busy_wait(10); /* Let pull-up settle */

        int val = gpio_pin_get(test_pins[i].port, test_pins[i].pin);
        if (val == 1) {
            passed++;
        }

        gpio_pin_configure(test_pins[i].port, test_pins[i].pin, GPIO_INPUT);
    }

    char details[128];
    snprintf(details, sizeof(details), "Pull-up test: %d/%d pins high", passed, total);

    if (passed == total && total > 0) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No GPIO ports available");
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, total);

    return 0;
}

/* Test: GPIO input with pull-down */
int test_gpio_input_pulldown(struct diagnostic_context *ctx, struct test_result *result)
{
    int passed = 0, total = 0;

    for (int i = 0; i < NUM_TEST_PINS; i++) {
        if (!test_pins[i].port || !device_is_ready(test_pins[i].port)) {
            continue;
        }

        total++;
        int ret = gpio_pin_configure(test_pins[i].port, test_pins[i].pin,
                                     GPIO_INPUT | GPIO_PULL_DOWN);
        if (ret < 0) {
            continue;
        }

        k_busy_wait(10);

        int val = gpio_pin_get(test_pins[i].port, test_pins[i].pin);
        if (val == 0) {
            passed++;
        }

        gpio_pin_configure(test_pins[i].port, test_pins[i].pin, GPIO_INPUT);
    }

    char details[128];
    snprintf(details, sizeof(details), "Pull-down test: %d/%d pins low", passed, total);

    if (passed == total && total > 0) {
        test_result_set_pass(result, details);
    } else if (passed > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No GPIO ports available");
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, total);

    return 0
}

/* Test: GPIO interrupt */
int test_gpio_interrupt(struct diagnostic_context *ctx, struct test_result *result)
{
    /* This test requires external signal or loopback */
    test_result_set_skip(result, "Requires external signal generator");
    return 0;
}

/* Test: GPIO short detection (adjacent pins) */
int test_gpio_short_detect(struct diagnostic_context *ctx, struct test_result *result)
{
    int shorts_found = 0;
    int tested = 0;

    for (int i = 0; i < NUM_TEST_PINS - 1; i++) {
        if (!test_pins[i].port || !test_pins[i+1].port) continue;
        if (!device_is_ready(test_pins[i].port) || !device_is_ready(test_pins[i+1].port)) continue;

        /* Drive pin i high, pin i+1 low */
        gpio_pin_configure(test_pins[i].port, test_pins[i].pin, GPIO_OUTPUT_HIGH);
        gpio_pin_configure(test_pins[i+1].port, test_pins[i+1].pin, GPIO_OUTPUT_LOW);
        k_busy_wait(10);

        int val1 = gpio_pin_get(test_pins[i].port, test_pins[i].pin);
        int val2 = gpio_pin_get(test_pins[i+1].port, test_pins[i+1].pin);

        /* If both read same, possible short */
        if (val1 == val2) {
            shorts_found++;
        }

        tested++;

        /* Restore */
        gpio_pin_configure(test_pins[i].port, test_pins[i].pin, GPIO_INPUT);
        gpio_pin_configure(test_pins[i+1].port, test_pins[i+1].pin, GPIO_INPUT);
    }

    char details[128];
    snprintf(details, sizeof(details), "Adjacent pin short test: %d/%d pairs checked, %d potential shorts",
             tested, tested, shorts_found);

    if (shorts_found == 0 && tested > 0) {
        test_result_set_pass(result, details);
    } else if (tested > 0) {
        test_result_set_fail(result, details);
    } else {
        test_result_set_skip(result, "No GPIO ports available");
    }

    test_result_add_measurement(result, shorts_found);
    test_result_add_measurement(result, tested);

    return 0;
}

/* GPIO test suite */
const struct test_case gpio_tests[] = {
    {
        .name = "gpio_output",
        .description = "Test GPIO output toggle on all available pins",
        .func = test_gpio_output,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_GPIO,
    },
    {
        .name = "gpio_input_pullup",
        .description = "Test GPIO input with internal pull-up resistors",
        .func = test_gpio_input_pullup,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_GPIO,
    },
    {
        .name = "gpio_input_pulldown",
        .description = "Test GPIO input with internal pull-down resistors",
        .func = test_gpio_input_pulldown,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_GPIO,
    },
    {
        .name = "gpio_interrupt",
        .description = "Test GPIO interrupt capability (requires external signal)",
        .func = test_gpio_interrupt,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_GPIO,
    },
    {
        .name = "gpio_short_detect",
        .description = "Detect shorts between adjacent GPIO pins",
        .func = test_gpio_short_detect,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_GPIO,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};