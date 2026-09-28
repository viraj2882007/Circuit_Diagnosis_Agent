/**
 * MCU Diagnostic Firmware - Main Entry Point
 * Runs peripheral self-tests and reports results via serial/UART
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
#define REPORT_BAUD_RATE 115200

static const struct device *uart_dev = DEVICE_DT_GET(TEST_UART_NODE);
static struct diagnostic_context diag_ctx;
static uint8_t report_buffer[CONFIG_DIAGNOSTIC_BUFFER_SIZE];

/* Test suite declarations */
extern const struct test_suite basic_tests[];
extern const struct test_suite gpio_tests[];
extern const struct test_suite analog_tests[];
extern const struct test_suite communication_tests[];
extern const struct test_suite timing_tests[];
extern const struct test_suite memory_tests[];
extern const struct test_suite clock_tests[];

/* Test suite mapping by name */
static const struct {
    const char *name;
    const struct test_suite *suite;
    bool required;
} test_suites[] = {
    {"basic", basic_tests, true},
    {"gpio", gpio_tests, false},
    {"analog", analog_tests, false},
    {"communication", communication_tests, false},
    {"timing", timing_tests, false},
    {"memory", memory_tests, false},
    {"clock", clock_tests, false},
    {NULL, NULL, false}  /* Sentinel */
};

int main(void)
{
    int ret;

    LOG_INF("MCU Diagnostic Firmware v%d starting...", DIAGNOSTIC_FIRMWARE_VERSION);

    /* Initialize diagnostic context */
    ret = diagnostic_init(&diag_ctx, uart_dev, report_buffer, sizeof(report_buffer));
    if (ret < 0) {
        LOG_ERR("Failed to initialize diagnostics: %d", ret);
        return ret;
    }

    /* Initialize reporting */
    reporting_init(uart_dev);

    /* Get device info */
    uint8_t dev_id[32];
    size_t id_len = sizeof(dev_id);
    hwinfo_get_device_id(dev_id, &id_len);
    diagnostic_set_device_id(&diag_ctx, dev_id, id_len);

    /* Send device info to host */
    diagnostic_send_device_info(&diag_ctx);

    /* Parse test suites from CMake configuration */
    char *enabled_suites = DIAGNOSTIC_TEST_SUITES;
    char *suite_name = strtok(enabled_suites, ";");
    
    LOG_INF("Starting diagnostic test suites...");

    while (suite_name != NULL) {
        /* Find suite */
        const struct test_suite *suite = NULL;
        bool required = false;
        
        for (int i = 0; test_suites[i].name != NULL; i++) {
            if (strcmp(test_suites[i].name, suite_name) == 0) {
                suite = test_suites[i].suite;
                required = test_suites[i].required;
                break;
            }
        }
        
        if (suite) {
            LOG_INF("Running suite: %s", suite_name);
            ret = diagnostic_run_suite(&diag_ctx, suite);
            if (ret < 0) {
                LOG_ERR("Suite %s failed: %d", suite_name, ret);
                if (required) {
                    LOG_ERR("Required suite failed, aborting");
                    break;
                }
            }
        } else {
            LOG_WRN("Unknown test suite: %s", suite_name);
        }
        
        suite_name = strtok(NULL, ";");
    }

    /* Send final report */
    LOG_INF("All tests complete, sending final report");
    diagnostic_send_final_report(&diag_ctx);

    /* Enter interactive shell for manual testing */
    LOG_INF("Entering interactive mode. Type 'help' for commands.");
    return 0;
}

/* Shell commands for interactive testing */
static int cmd_run_test(const struct shell *shell, size_t argc, char **argv)
{
    if (argc < 2) {
        shell_print(shell, "Usage: test <test_name>");
        return -EINVAL;
    }

    const char *test_name = argv[1];
    struct test_result result;

    int ret = diagnostic_run_single_test(&diag_ctx, test_name, &result);
    if (ret < 0) {
        shell_print(shell, "Test not found or failed to run: %s", test_name);
        return ret;
    }

    shell_print(shell, "Test: %s - %s", result.name,
                result.status == TEST_PASS ? "PASS" : "FAIL");
    if (result.details[0]) {
        shell_print(shell, "Details: %s", result.details);
    }

    return 0;
}

static int cmd_list_tests(const struct shell *shell, size_t argc, char **argv)
{
    shell_print(shell, "Available tests:");
    for (int i = 0; test_suites[i].name != NULL; i++) {
        shell_print(shell, "  Suite: %s", test_suites[i].name);
        for (int j = 0; j < test_suites[i].suite[j].name != NULL; j++) {
            shell_print(shell, "    %s", test_suites[i].suite[j].name);
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
    SHELL_CMD(run, NULL, "Run specific test", cmd_run_test),
    SHELL_CMD(list, NULL, "List all tests", cmd_list_tests),
    SHELL_CMD(report, NULL, "Send final report", cmd_get_report),
    SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(diag, &diagnostic_cmds, "Diagnostic commands", NULL);