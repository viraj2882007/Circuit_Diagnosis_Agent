/**
 * Memory Tests - Flash, RAM, EEPROM testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/storage/flash_map.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(flash0), okay)
#define FLASH_DEV DEVICE_DT_GET(DT_NODELABEL(flash0))
#else
#define FLASH_DEV NULL
#endif

/* Test patterns for memory testing */
static const uint32_t test_patterns[] = {
    0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555,
    0xDEADBEEF, 0xCAFEBABE, 0x12345678, 0x87654321,
};

/* Test: Flash write/read/erase */
int test_flash_write_read(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!FLASH_DEV || !device_is_ready(FLASH_DEV)) {
        test_result_set_skip(result, "Flash device not available");
        return 0;
    }

    const struct flash_parameters *params = flash_get_parameters(FLASH_DEV);
    if (!params) {
        test_result_set_fail(result, "Failed to get flash parameters");
        return 0;
    }

    /* Find a safe test area (last sector typically) */
    off_t test_addr = params->size - params->erase_value * 2;  /* Conservative */
    size_t test_size = 256;  /* Small test area */

    /* Erase test sector */
    int ret = flash_erase(FLASH_DEV, test_addr, params->erase_value);
    if (ret < 0) {
        test_result_set_fail(result, "Flash erase failed");
        return 0;
    }

    /* Write test patterns */
    uint8_t write_buf[256];
    uint8_t read_buf[256];
    int passed = 0;

    for (int i = 0; i < 8; i++) {
        /* Fill buffer with pattern */
        for (int j = 0; j < 256; j += 4) {
            *(uint32_t *)(write_buf + j) = test_patterns[i];
        }

        ret = flash_write(FLASH_DEV, test_addr, write_buf, sizeof(write_buf));
        if (ret < 0) {
            continue;
        }

        ret = flash_read(FLASH_DEV, test_addr, read_buf, sizeof(read_buf));
        if (ret < 0) {
            continue;
        }

        if (memcmp(write_buf, read_buf, sizeof(write_buf)) == 0) {
            passed++;
        }
    }

    /* Clean up - erase again */
    flash_erase(FLASH_DEV, test_addr, params->erase_value);

    char details[128];
    snprintf(details, sizeof(details), "Flash R/W test: %d/8 patterns verified", passed);

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

/* Test: Flash erase */
int test_flash_erase(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!FLASH_DEV || !device_is_ready(FLASH_DEV)) {
        test_result_set_skip(result, "Flash device not available");
        return 0;
    }

    const struct flash_parameters *params = flash_get_parameters(FLASH_DEV);
    off_t test_addr = params->size - params->erase_value;
    size_t test_size = params->erase_value;

    /* Write some data first */
    uint8_t data[256];
    memset(data, 0xFF, sizeof(data));
    flash_write(FLASH_DEV, test_addr, data, sizeof(data));

    /* Erase */
    int ret = flash_erase(FLASH_DEV, test_addr, test_size);
    if (ret < 0) {
        test_result_set_fail(result, "Flash erase failed");
        return 0;
    }

    /* Verify erased */
    uint8_t read_buf[256];
    flash_read(FLASH_DEV, test_addr, read_buf, sizeof(read_buf));

    uint8_t erased_val = params->erase_value;
    bool all_erased = true;
    for (int i = 0; i < 256; i++) {
        if (read_buf[i] != erased_val) {
            all_erased = false;
            break;
        }
    }

    char details[128];
    snprintf(details, sizeof(details), "Flash erase: %s", all_erased ? "verified" : "FAILED");

    if (all_erased) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    return 0;
}

/* Test: RAM March test */
int test_ram_march(struct diagnostic_context *ctx, struct test_result *result)
{
    /* Test a small RAM region */
    volatile uint32_t *ram = (volatile uint32_t *)0x20000000;  /* Start of RAM */
    size_t test_words = 1024;  /* Test 4KB */
    int errors = 0;

    /* March C- algorithm (simplified) */
    for (size_t i = 0; i < test_words; i++) {
        ram[i] = 0x00000000;
    }
    for (size_t i = 0; i < test_words; i++) {
        if (ram[i] != 0x00000000) errors++;
        ram[i] = 0xFFFFFFFF;
    }
    for (size_t i = 0; i < test_words; i++) {
        if (ram[i] != 0xFFFFFFFF) errors++;
        ram[i] = 0xAAAAAAAA;
    }
    for (size_t i = 0; i < test_words; i++) {
        if (ram[i] != 0xAAAAAAAA) errors++;
        ram[i] = 0x55555555;
    }
    for (size_t i = 0; i < test_words; i++) {
        if (ram[i] != 0x55555555) errors++;
    }

    char details[128];
    snprintf(details, sizeof(details), "RAM March test: %d errors in %zu words", errors, test_words);

    if (errors == 0) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, errors);
    test_result_add_measurement(result, test_words);

    return 0;
}

/* Test: Extended RAM test (walking 1s/0s) */
int test_ram_extended_march(struct diagnostic_context *ctx, struct test_result *result)
{
    volatile uint32_t *ram = (volatile uint32_t *)0x20000000;
    size_t test_words = 4096;  /* 16KB */
    int errors = 0;

    /* Walking 1s */
    for (int bit = 0; bit < 32; bit++) {
        uint32_t pattern = 1u << bit;
        for (size_t i = 0; i < test_words; i++) {
            ram[i] = pattern;
        }
        for (size_t i = 0; i < test_words; i++) {
            if (ram[i] != pattern) errors++;
        }
    }

    /* Walking 0s */
    for (int bit = 0; bit < 32; bit++) {
        uint32_t pattern = ~(1u << bit);
        for (size_t i = 0; i < test_words; i++) {
            ram[i] = pattern;
        }
        for (size_t i = 0; i < test_words; i++) {
            if (ram[i] != pattern) errors++;
        }
    }

    char details[128];
    snprintf(details, sizeof(details), "Extended RAM test: %d errors", errors);

    if (errors == 0) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, errors);

    return 0;
}

/* Memory test suite */
const struct test_case memory_tests[] = {
    {
        .name = "flash_write_read",
        .description = "Flash write/read/verify with multiple patterns",
        .func = test_flash_write_read,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_FLASH,
    },
    {
        .name = "flash_erase",
        .description = "Flash sector erase verification",
        .func = test_flash_erase,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_FLASH,
    },
    {
        .name = "ram_march",
        .description = "RAM March C- test on 4KB",
        .func = test_ram_march,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_RAM,
    },
    {
        .name = "ram_extended_march",
        .description = "Extended RAM walking 1s/0s test on 16KB",
        .func = test_ram_extended_march,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_RAM,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};