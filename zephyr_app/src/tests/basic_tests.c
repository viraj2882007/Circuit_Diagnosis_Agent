/**
 * Basic Tests - Core CPU and system tests
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/drivers/entropy.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(entropy), okay)
#define ENTROPY_DEV DEVICE_DT_GET(DT_NODELABEL(entropy))
#else
#define ENTROPY_DEV NULL
#endif

/* Test: CPU identification */
int test_cpu_id(struct diagnostic_context *ctx, struct test_result *result)
{
    uint8_t dev_id[32] = {0};
    int id_bytes = (int)hwinfo_get_device_id(dev_id, sizeof(dev_id));

    char details[256];
    if (id_bytes > 0) {
        size_t id_len = (size_t)id_bytes;
        if (id_len > sizeof(dev_id)) {
            id_len = sizeof(dev_id);
        }
        char id_str[65] = {0};
        for (size_t i = 0; i < id_len; i++) {
            snprintf(id_str + i * 2, sizeof(id_str) - i * 2, "%02X", dev_id[i]);
        }
        snprintf(details, sizeof(details), "Device ID (%zu bytes): %s", id_len, id_str);
        test_result_set_pass(result, details);
        test_result_add_measurement(result, (uint32_t)id_len);
    } else if (id_bytes == -ENOSYS || id_bytes == -ENOTSUP || id_bytes == 0) {
        test_result_set_skip(result, "Unique hardware ID is not implemented by this board.");
    } else {
        snprintf(details, sizeof(details), "Hardware-ID read failed: %d", id_bytes);
        test_result_set_fail(result, details);
    }
    return 0;
}

/* Reserved storage keeps the quick RAM test away from stack, heap, and live data. */
static volatile uint32_t quick_ram_test_buffer[256];

/* Test: RAM March test (quick) */
int test_ram_march_quick(struct diagnostic_context *ctx, struct test_result *result)
{
    volatile uint32_t *ram = quick_ram_test_buffer;
    const size_t test_words = sizeof(quick_ram_test_buffer) / sizeof(quick_ram_test_buffer[0]);
    int errors = 0;

    for (size_t i = 0; i < test_words; i++) ram[i] = 0;
    for (size_t i = 0; i < test_words; i++) if (ram[i] != 0) errors++;
    for (size_t i = 0; i < test_words; i++) ram[i] = 0xFFFFFFFF;
    for (size_t i = 0; i < test_words; i++) if (ram[i] != 0xFFFFFFFF) errors++;

    char details[128];
    snprintf(details, sizeof(details),
             "Quick RAM-buffer test: %d errors in %zu reserved words (not a whole-RAM test)",
             errors, test_words);

    if (errors == 0) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, errors);
    test_result_add_measurement(result, test_words);
    return 0;
}

/* Test: Flash ID / JEDEC */
int test_flash_id(struct diagnostic_context *ctx, struct test_result *result)
{
#if DT_NODE_HAS_STATUS(DT_NODELABEL(flash0), okay)
    const struct device *flash_dev = DEVICE_DT_GET(DT_NODELABEL(flash0));
    if (!device_is_ready(flash_dev)) {
        test_result_set_skip(result, "Flash not available");
        return 0;
    }

    const struct flash_parameters *params = flash_get_parameters(flash_dev);
    if (!params) {
        test_result_set_fail(result, "Flash parameters not available");
        return 0;
    }

    char details[256];
    snprintf(details, sizeof(details),
             "Flash device ready: erase_value=0x%02X, write_block=%zu bytes; capacity not reported by this API",
             params->erase_value, params->write_block_size);

    test_result_set_pass(result, details);
    test_result_add_measurement(result, params->erase_value);
    test_result_add_measurement(result, params->write_block_size);
#else
    test_result_set_skip(result, "Flash not available");
#endif
    return 0;
}

/* Test: Clock check */
int test_clock_check(struct diagnostic_context *ctx, struct test_result *result)
{
    uint32_t freq = sys_clock_hw_cycles_per_sec();

    char details[128];
    snprintf(details, sizeof(details), "System clock: %u Hz (%u.%02u MHz)",
             freq, freq / 1000000U, (freq % 1000000U) / 10000U);

    if (freq > 1000000 && freq < 500000000) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, freq);
    return 0;
}

/* Test: GPIO toggle (quick) */
int test_gpio_toggle(struct diagnostic_context *ctx, struct test_result *result)
{
#if DT_NODE_HAS_STATUS(DT_NODELABEL(gpioa), okay)
    const struct device *gpio = DEVICE_DT_GET(DT_NODELABEL(gpioa));
    if (!device_is_ready(gpio)) {
        test_result_set_skip(result, "GPIO not available");
        return 0;
    }

    int ret = gpio_pin_configure(gpio, 5, GPIO_OUTPUT_INACTIVE);  /* LED pin typically */
    if (ret < 0) {
        test_result_set_fail(result, "GPIO configure failed");
        return 0;
    }

    for (int i = 0; i < 10; i++) {
        gpio_pin_set(gpio, 5, 1);
        k_busy_wait(50000);
        gpio_pin_set(gpio, 5, 0);
        k_busy_wait(50000);
    }

    test_result_set_pass(result, "GPIO toggle test passed (10 cycles)");
#else
    test_result_set_skip(result, "GPIO not available");
#endif
    return 0;
}

/* Test: Entropy/RNG */
int test_entropy(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!ENTROPY_DEV || !device_is_ready(ENTROPY_DEV)) {
        test_result_set_skip(result, "Entropy/RNG not available");
        return 0;
    }

    uint8_t entropy_buf[32];
    int ret = entropy_get_entropy(ENTROPY_DEV, entropy_buf, sizeof(entropy_buf));

    char details[128];
    if (ret == 0) {
        snprintf(details, sizeof(details), "Entropy: %d bytes generated", ret);
        test_result_set_pass(result, details);
    } else {
        snprintf(details, sizeof(details), "Entropy failed: %d", ret);
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, ret);
    return 0;
}

/* Basic test suite */
const struct test_case basic_tests[] = {
    {
        .name = "cpu_id",
        .description = "Read CPU/device identification",
        .func = test_cpu_id,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    {
        .name = "ram_march_quick",
        .description = "Quick RAM March test (1KB)",
        .func = test_ram_march_quick,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_RAM,
    },
    {
        .name = "flash_id",
        .description = "Read flash parameters and JEDEC ID",
        .func = test_flash_id,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_FLASH,
    },
    {
        .name = "clock_check",
        .description = "Verify system clock frequency",
        .func = test_clock_check,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    {
        .name = "gpio_toggle",
        .description = "Quick GPIO toggle test (PA5/LED)",
        .func = test_gpio_toggle,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_GPIO,
    },
    {
        .name = "entropy",
        .description = "Hardware entropy/RNG test",
        .func = test_entropy,
        .timeout_ms = 1000,
        .required_peripherals = 0,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};