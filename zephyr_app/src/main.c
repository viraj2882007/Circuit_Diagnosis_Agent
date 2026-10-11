/**
 * MCU Diagnostic Firmware - Main Entry Point
 * Runs peripheral self-tests and reports results via serial/UART.
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"
#include "reporting.h"
#include "serial_protocol.h"

LOG_MODULE_REGISTER(diagnostic_main, LOG_LEVEL_INF);

#define TEST_UART_NODE DT_CHOSEN(zephyr_console)

static const struct device *uart_dev = DEVICE_DT_GET(TEST_UART_NODE);
static struct diagnostic_context diag_ctx;
static uint8_t report_buffer[CONFIG_DIAGNOSTIC_BUFFER_SIZE];

/* Each test module exports a sentinel-terminated array of test_case records. */
extern const struct test_case basic_tests[];
extern const struct test_case gpio_tests[];
extern const struct test_case adc_tests[];
extern const struct test_case dac_tests[];
extern const struct test_case uart_tests[];
extern const struct test_case spi_tests[];
extern const struct test_case i2c_tests[];
extern const struct test_case timer_tests[];
extern const struct test_case memory_tests[];
extern const struct test_case clock_tests[];

struct suite_entry {
    const char *name;
    const struct test_case *cases;
    bool required;
};

/* Suite names map to the actual arrays exported by the firmware modules. */
static const struct suite_entry test_suites[] = {
    {"basic", basic_tests, true},
    {"gpio", gpio_tests, false},
    {"adc", adc_tests, false},
    {"dac", dac_tests, false},
    {"uart", uart_tests, false},
    {"spi", spi_tests, false},
    {"i2c", i2c_tests, false},
    {"timing", timer_tests, false},
    {"memory", memory_tests, false},
    {"clock", clock_tests, false},
    {NULL, NULL, false}
};

static int count_test_cases(const struct test_case *cases)
{
    int count = 0;

    if (cases == NULL) {
        return 0;
    }
    while (cases[count].name != NULL) {
        count++;
    }
    return count;
}

int main(void)
{
    int ret;

    LOG_INF("MCU Diagnostic Firmware v%d starting...", DIAGNOSTIC_FIRMWARE_VERSION);

    ret = diagnostic_init(&diag_ctx, uart_dev, report_buffer, sizeof(report_buffer));
    if (ret < 0) {
        LOG_ERR("Failed to initialize diagnostics: %d", ret);
        return ret;
    }

    reporting_init(uart_dev);

    uint8_t dev_id[32] = {0};
    size_t id_len = 0;
    int id_bytes = (int)hwinfo_get_device_id(dev_id, sizeof(dev_id));
    if (id_bytes < 0) {
        LOG_WRN("MCU device ID unavailable: %d", id_bytes);
    } else if ((size_t)id_bytes > sizeof(dev_id)) {
        id_len = sizeof(dev_id);
    } else {
        id_len = (size_t)id_bytes;
    }
    diagnostic_set_device_id(&diag_ctx, dev_id, id_len);
    diagnostic_send_device_info(&diag_ctx);

    /* CMake expands this list into a string literal; copy it before strtok mutates it. */
    char enabled_suites[] = DIAGNOSTIC_TEST_SUITES;
    char *suite_name = strtok(enabled_suites, ",");

    LOG_INF("Starting diagnostic test suites...");
    while (suite_name != NULL) {
        const struct suite_entry *entry = NULL;
        for (size_t i = 0; test_suites[i].name != NULL; i++) {
            if (strcmp(test_suites[i].name, suite_name) == 0) {
                entry = &test_suites[i];
                break;
            }
        }

        if (entry != NULL) {
            struct test_suite suite = {
                .name = entry->name,
                .tests = entry->cases,
                .test_count = count_test_cases(entry->cases),
                .required = entry->required,
            };
            if (suite.test_count == 0) {
                LOG_WRN("Suite %s has no test cases", suite_name);
            } else {
                LOG_INF("Running suite: %s (%d tests)", suite.name, suite.test_count);
                ret = diagnostic_run_suite(&diag_ctx, &suite);
                if (ret < 0) {
                    LOG_ERR("Suite %s failed: %d", suite_name, ret);
                    if (entry->required) {
                        LOG_ERR("Required suite failed, aborting remaining tests");
                        break;
                    }
                }
            }
        } else {
            LOG_WRN("Unknown test suite: %s", suite_name);
        }

        suite_name = strtok(NULL, ",");
    }

    LOG_INF("All tests complete, sending final report");
    diagnostic_send_final_report(&diag_ctx);
    LOG_INF("Diagnostic tests completed. Type 'diag list' in the shell to inspect test names.");
    return 0;
}

/* Shell commands for interactive testing. */
static int cmd_run_test(const struct shell *shell, size_t argc, char **argv)
{
    if (argc < 2) {
        shell_print(shell, "Usage: diag run <test_name>");
        return -EINVAL;
    }

    struct test_result result;
    int ret = diagnostic_run_single_test(&diag_ctx, argv[1], &result);
    if (ret < 0) {
        shell_print(shell, "Test not found or could not run: %s", argv[1]);
        return ret;
    }

    const char *status = "UNKNOWN";
    if (result.status == TEST_PASS) {
        status = "PASS";
    } else if (result.status == TEST_FAIL) {
        status = "FAIL";
    } else if (result.status == TEST_SKIP) {
        status = "SKIP";
    } else if (result.status == TEST_ERROR) {
        status = "ERROR";
    }
    shell_print(shell, "Test: %s - %s", result.name, status);
    if (result.details[0] != '\0') {
        shell_print(shell, "Details: %s", result.details);
    }
    return 0;
}

static int cmd_list_tests(const struct shell *shell, size_t argc, char **argv)
{
    shell_print(shell, "Available tests:");
    for (size_t i = 0; test_suites[i].name != NULL; i++) {
        shell_print(shell, "  Suite: %s", test_suites[i].name);
        for (int j = 0; test_suites[i].cases[j].name != NULL; j++) {
            shell_print(shell, "    %s", test_suites[i].cases[j].name);
        }
    }
    return 0;
}

static int cmd_get_report(const struct shell *shell, size_t argc, char **argv)
{
    diagnostic_send_final_report(&diag_ctx);
    shell_print(shell, "Report sent via UART");
    return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(diagnostic_cmds,
    SHELL_CMD(run, NULL, "Run a specific test by name", cmd_run_test),
    SHELL_CMD(list, NULL, "List available test suites and tests", cmd_list_tests),
    SHELL_CMD(report, NULL, "Send the final report over UART", cmd_get_report),
    SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(diag, &diagnostic_cmds, "MCU diagnostic commands", NULL);
