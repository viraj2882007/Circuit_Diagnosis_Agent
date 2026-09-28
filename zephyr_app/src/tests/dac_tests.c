/**
 * DAC Tests - Digital-to-Analog Converter testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/dac.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

#if DT_NODE_HAS_STATUS(DT_NODELABEL(dac), okay)
#define DAC_DEV DEVICE_DT_GET(DT_NODELABEL(dac))
#else
#define DAC_DEV NULL
#endif

#define DAC_CHANNEL_0 0
#define DAC_CHANNEL_1 1
#define DAC_RESOLUTION 12
#define DAC_MAX_VALUE ((1 << DAC_RESOLUTION) - 1)

/* Test: DAC output voltage levels */
int test_dac_output(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!DAC_DEV || !device_is_ready(DAC_DEV)) {
        test_result_set_skip(result, "DAC device not available");
        return 0;
    }

    const uint16_t test_values[] = {
        0,
        DAC_MAX_VALUE / 4,
        DAC_MAX_VALUE / 2,
        3 * DAC_MAX_VALUE / 4,
        DAC_MAX_VALUE,
    };

    int passed = 0;

    for (int ch = 0; ch < 2; ch++) {
        for (int i = 0; i < 5; i++) {
            int ret = dac_write_value(DAC_DEV, ch, test_values[i]);
            if (ret < 0) {
                char details[128];
                snprintf(details, sizeof(details), "DAC ch%d write failed at value %u",
                         ch, test_values[i]);
                test_result_set_fail(result, details);
                return 0;
            }

            k_busy_wait(1000); /* Let output settle */

            /* In real test, would read back via ADC on same pin */
            /* For now, just verify write succeeds */
            passed++;
        }
    }

    char details[128];
    snprintf(details, sizeof(details), "DAC output test: %d/10 writes successful", passed);

    if (passed == 10) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, passed);
    test_result_add_measurement(result, 10);

    return 0;
}

/* Test: DAC to ADC loopback (requires external wiring or internal connection) */
int test_dac_adc_loopback(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!DAC_DEV || !device_is_ready(DAC_DEV)) {
        test_result_set_skip(result, "DAC device not available");
        return 0;
    }

#if DT_NODE_HAS_STATUS(DT_NODELABEL(adc), okay)
#define ADC_DEV DEVICE_DT_GET(DT_NODELABEL(adc))
#else
#define ADC_DEV NULL
#endif

    if (!ADC_DEV || !device_is_ready(ADC_DEV)) {
        test_result_set_skip(result, "ADC not available for loopback");
        return 0;
    }

    /* This test requires DAC output connected to ADC input */
    /* Typically DAC_OUT1 -> ADC_INx with external jumper */
    test_result_set_skip(result, "Requires DAC_OUT to ADC_IN jumper");
    return 0;
}

/* DAC test suite */
const struct test_case dac_tests[] = {
    {
        .name = "dac_output",
        .description = "Test DAC output at multiple voltage levels",
        .func = test_dac_output,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_DAC,
    },
    {
        .name = "dac_adc_loopback",
        .description = "DAC to ADC loopback test (requires jumper)",
        .func = test_dac_adc_loopback,
        .timeout_ms = 3000,
        .required_peripherals = PERIPH_DAC | PERIPH_ADC,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};