/**
 * Reporting - Test result reporting and serialization
 */

#ifndef REPORTING_H
#define REPORTING_H

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>
#include "test_framework.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Report message types */
#define REPORT_MAGIC 0x44494147  /* "DIAG" */
#define REPORT_VERSION 1

typedef enum {
    REPORT_TYPE_TEST_RESULT = 0x01,
    REPORT_TYPE_SUITE_SUMMARY = 0x02,
    REPORT_TYPE_FINAL_REPORT = 0x03,
    REPORT_TYPE_DEVICE_INFO = 0x04,
    REPORT_TYPE_ERROR = 0xFF,
} report_type_t;

/* Report header */
struct __packed report_header {
    uint32_t magic;
    uint8_t version;
    uint8_t type;
    uint16_t length;
    uint32_t timestamp;
    uint32_t sequence;
};

/* Test result report payload */
struct __packed test_result_report {
    struct report_header header;
    char test_name[64];
    uint8_t status;
    uint32_t duration_ms;
    uint32_t measurements[8];
    uint8_t measurement_count;
    char details[256];
};

/* Suite summary report payload */
struct __packed suite_summary_report {
    struct report_header header;
    char suite_name[32];
    uint16_t passed;
    uint16_t failed;
    uint16_t skipped;
    uint32_t duration_ms;
};

/* Final report payload */
struct __packed final_report {
    struct report_header header;
    uint8_t device_id[32];
    uint8_t device_id_len;
    uint32_t firmware_version;
    uint32_t total_tests;
    uint16_t total_passed;
    uint16_t total_failed;
    uint16_t total_skipped;
    uint32_t total_duration_ms;
    uint32_t crc32;
};

/* Initialize reporting */
void reporting_init(const struct device *uart_dev);

/* Send test result */
void diagnostic_send_test_result(struct diagnostic_context *ctx,
                                 const struct test_result *result);

/* Send suite summary */
void diagnostic_send_suite_summary(struct diagnostic_context *ctx,
                                   const char *suite_name,
                                   int passed, int failed, int skipped);

/* Send final report */
int diagnostic_send_final_report(struct diagnostic_context *ctx);

/* Send device info */
void diagnostic_send_device_info(struct diagnostic_context *ctx);

/* Calculate CRC32 */
uint32_t crc32_calculate(const uint8_t *data, size_t len, uint32_t crc);

#ifdef __cplusplus
}
#endif

#endif /* REPORTING_H */