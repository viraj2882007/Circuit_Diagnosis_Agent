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

/*
 * Non-destructive by default: generic firmware must never guess that the last flash
 * sector is unused. Destructive flash tests require a board-specific reserved partition
 * and a separately reviewed recovery procedure, neither of which is available here.
 */
int test_flash_write_read(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(
        result,
        "Flash write/read test disabled: no board-specific reserved test partition or recovery plan."
    );
    return 0;
}

int test_flash_erase(struct diagnostic_context *ctx, struct test_result *result)
{
    test_result_set_skip(
        result,
        "Flash erase test disabled: protecting firmware and user data from destructive writes."
    );
    return 0;
}

static volatile uint32_t memory_test_buffer[4096]; /* 16 KiB explicitly reserved in .bss. */

/* Test: RAM March test */
int test_ram_march(struct diagnostic_context *ctx, struct test_result *result)
{
    /* Test only the reserved buffer; never overwrite a guessed RAM address. */
    volatile uint32_t *ram = memory_test_buffer;
    const size_t test_words = 1024; /* Test 4 KiB of reserved .bss. */
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
    snprintf(details, sizeof(details), "RAM-buffer March test: %d errors in %zu reserved words (not a whole-RAM test)", errors, test_words);

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
    /* Reuse only the statically reserved 16 KiB test buffer. */
    volatile uint32_t *ram = memory_test_buffer;
    const size_t test_words = sizeof(memory_test_buffer) / sizeof(memory_test_buffer[0]);
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
    snprintf(details, sizeof(details), "Extended reserved RAM-buffer walking-bit test: %d errors (not a whole-RAM test)", errors);

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
        .description = "Non-destructive placeholder; skipped unless a board-specific safe partition/recovery flow is implemented",
        .func = test_flash_write_read,
        .timeout_ms = 5000,
        .required_peripherals = PERIPH_FLASH,
    },
    {
        .name = "flash_erase",
        .description = "Destructive flash erase intentionally disabled in generic firmware",
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