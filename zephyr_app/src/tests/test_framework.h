/**
 * Test Framework - Core definitions for diagnostic tests
 */

#ifndef TEST_FRAMEWORK_H
#define TEST_FRAMEWORK_H

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Test status codes */
typedef enum {
    TEST_PASS = 0,
    TEST_FAIL = 1,
    TEST_SKIP = 2,
    TEST_ERROR = -1,
} test_status_t;

/* Test function signature */
typedef int (*test_func_t)(struct diagnostic_context *ctx, struct test_result *result);

/* Individual test definition */
struct test_case {
    const char *name;
    const char *description;
    test_func_t func;
    uint32_t timeout_ms;          /* Test timeout in ms */
    uint32_t required_peripherals; /* Bitmask of required peripherals */
};

/* Test suite definition */
struct test_suite {
    const char *name;
    const struct test_case *tests;
    int test_count;
    bool required;                /* If true, failure aborts all testing */
};

/* Test result structure */
struct test_result {
    char name[64];
    test_status_t status;
    char details[256];
    uint32_t duration_ms;
    uint32_t timestamp;
    uint32_t measurements[8];     /* Test-specific measurements */
    int measurement_count;
};

/* Diagnostic context - holds state during test run */
struct diagnostic_context {
    const struct device *uart_dev;
    uint8_t *report_buffer;
    size_t buffer_size;
    size_t buffer_used;

    struct test_result *results;
    int result_count;
    int result_capacity;

    uint8_t device_id[32];
    size_t device_id_len;

    uint32_t start_time;
    uint32_t suite_start_time;

    bool interactive_mode;
};

/* Peripheral bitmasks for test requirements */
#define PERIPH_GPIO       (1 << 0)
#define PERIPH_ADC        (1 << 1)
#define PERIPH_DAC        (1 << 2)
#define PERIPH_UART       (1 << 3)
#define PERIPH_SPI        (1 << 4)
#define PERIPH_I2C        (1 << 5)
#define PERIPH_TIMER      (1 << 6)
#define PERIPH_PWM        (1 << 7)
#define PERIPH_FLASH      (1 << 8)
#define PERIPH_RAM        (1 << 9)
#define PERIPH_USB        (1 << 10)
#define PERIPH_CAN        (1 << 11)
#define PERIPH_ETH        (1 << 12)
#define PERIPH_WIFI       (1 << 13)
#define PERIPH_BT         (1 << 14)

/* Core framework functions */
int diagnostic_init(struct diagnostic_context *ctx,
                    const struct device *uart_dev,
                    uint8_t *buffer, size_t buffer_size);

void diagnostic_deinit(struct diagnostic_context *ctx);

int diagnostic_run_suite(struct diagnostic_context *ctx,
                         const struct test_suite *suite);

int diagnostic_run_single_test(struct diagnostic_context *ctx,
                               const char *test_name,
                               struct test_result *result);

void diagnostic_set_device_id(struct diagnostic_context *ctx,
                              const uint8_t *id, size_t len);

int diagnostic_send_final_report(struct diagnostic_context *ctx);

/* Helper functions for tests */
uint32_t diagnostic_get_time_ms(void);
void diagnostic_delay_ms(uint32_t ms);

void test_result_init(struct test_result *result, const char *name);
void test_result_set_pass(struct test_result *result, const char *details);
void test_result_set_fail(struct test_result *result, const char *details);
void test_result_set_skip(struct test_result *result, const char *details);
void test_result_add_measurement(struct test_result *result, uint32_t value);

bool gpio_pin_test(const struct device *port, uint32_t pin,
                   gpio_flags_t flags, const char *pin_name,
                   struct test_result *result);

int uart_loopback_test(const struct device *uart_dev,
                       const char *test_name,
                       struct test_result *result);

#ifdef __cplusplus
}
#endif

#endif /* TEST_FRAMEWORK_H */