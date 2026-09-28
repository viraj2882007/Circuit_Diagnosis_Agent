/**
 * ADC Tests - Analog-to-Digital Converter testing
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/adc.h>
#include <string.h>
#include <stdio.h>

#include "test_framework.h"

/* ADC channel configuration */
#if DT_NODE_HAS_STATUS(DT_NODELABEL(adc), okay)
#define ADC_DEV DEVICE_DT_GET(DT_NODELABEL(adc))
#else
#define ADC_DEV NULL
#endif

/* Internal temperature sensor channel (common across MCUs) */
#define ADC_TEMP_CHANNEL 16  /* Typically channel 16 for internal temp */
#define ADC_VREF_CHANNEL 17  /* Typically channel 17 for VREF */

static const struct adc_channel_cfg temp_channel_cfg = {
    .gain = ADC_GAIN_1,
    .reference = ADC_REF_INTERNAL,
    .acquisition_time = ADC_ACQ_TIME_DEFAULT,
    .channel_id = ADC_TEMP_CHANNEL,
    .differential = 0,
};

static const struct adc_channel_cfg vref_channel_cfg = {
    .gain = ADC_GAIN_1,
    .reference = ADC_REF_INTERNAL,
    .acquisition_time = ADC_ACQ_TIME_DEFAULT,
    .channel_id = ADC_VREF_CHANNEL,
    .differential = 0,
};

static const struct adc_channel_cfg ext_channel_cfg = {
    .gain = ADC_GAIN_1,
    .reference = ADC_REF_INTERNAL,
    .acquisition_time = ADC_ACQ_TIME_DEFAULT,
    .channel_id = 0,  /* External channel 0 */
    .differential = 0,
};

/* Test: Internal temperature sensor */
int test_adc_internal_temp(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!ADC_DEV || !device_is_ready(ADC_DEV)) {
        test_result_set_skip(result, "ADC device not available");
        return 0;
    }

    int ret = adc_channel_setup(ADC_DEV, &temp_channel_cfg);
    if (ret < 0) {
        test_result_set_fail(result, "Failed to setup temperature channel");
        return 0;
    }

    struct adc_sequence sequence = {
        .channels = BIT(ADC_TEMP_CHANNEL),
        .buffer = &(uint16_t){0},
        .buffer_size = sizeof(uint16_t),
        .resolution = 12,
    };

    ret = adc_read(ADC_DEV, &sequence);
    if (ret < 0) {
        test_result_set_fail(result, "ADC read failed");
        return 0;
    }

    uint16_t raw = *(uint16_t *)sequence.buffer;
    float voltage = (raw * 3.3f) / 4095.0f;

    /* Temperature calculation (STM32 formula, adjust per MCU) */
    /* Typical: V25 = 0.76V, Avg_Slope = 2.5mV/°C */
    float temp_c = ((voltage - 0.76f) / 0.0025f) + 25.0f;

    char details[128];
    snprintf(details, sizeof(details),
             "Raw: %u, Voltage: %.3fV, Temp: %.1f°C", raw, voltage, temp_c);

    /* Sanity check: -40 to 125°C */
    if (temp_c > -40.0f && temp_c < 125.0f) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, raw);
    test_result_add_measurement(result, (uint32_t)(voltage * 1000));
    test_result_add_measurement(result, (uint32_t)(temp_c * 10));

    return 0;
}

/* Test: Internal voltage reference */
int test_adc_vref(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!ADC_DEV || !device_is_ready(ADC_DEV)) {
        test_result_set_skip(result, "ADC device not available");
        return 0;
    }

    int ret = adc_channel_setup(ADC_DEV, &vref_channel_cfg);
    if (ret < 0) {
        test_result_set_fail(result, "Failed to setup VREF channel");
        return 0;
    }

    struct adc_sequence sequence = {
        .channels = BIT(ADC_VREF_CHANNEL),
        .buffer = &(uint16_t){0},
        .buffer_size = sizeof(uint16_t),
        .resolution = 12,
    };

    ret = adc_read(ADC_DEV, &sequence);
    if (ret < 0) {
        test_result_set_fail(result, "ADC read failed");
        return 0;
    }

    uint16_t raw = *(uint16_t *)sequence.buffer;
    float voltage = (raw * 3.3f) / 4095.0f;

    char details[128];
    snprintf(details, sizeof(details), "VREF Raw: %u, Voltage: %.3fV", raw, voltage);

    /* VREF should be around 1.2V (internal reference) */
    if (voltage > 1.0f && voltage < 1.4f) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, raw);
    test_result_add_measurement(result, (uint32_t)(voltage * 1000));

    return 0;
}

/* Test: External ADC channel (requires known voltage on pin) */
int test_adc_external(struct diagnostic_context *ctx, struct test_result *result)
{
    if (!ADC_DEV || !device_is_ready(ADC_DEV)) {
        test_result_set_skip(result, "ADC device not available");
        return 0;
    }

    int ret = adc_channel_setup(ADC_DEV, &ext_channel_cfg);
    if (ret < 0) {
        test_result_set_fail(result, "Failed to setup external channel");
        return 0;
    }

    struct adc_sequence sequence = {
        .channels = BIT(0),
        .buffer = &(uint16_t){0},
        .buffer_size = sizeof(uint16_t),
        .resolution = 12,
    };

    /* Take multiple samples */
    uint32_t sum = 0;
    const int samples = 10;

    for (int i = 0; i < samples; i++) {
        ret = adc_read(ADC_DEV, &sequence);
        if (ret < 0) {
            test_result_set_fail(result, "ADC read failed");
            return 0;
        }
        sum += *(uint16_t *)sequence.buffer;
        k_busy_wait(100);
    }

    uint16_t avg = sum / samples;
    float voltage = (avg * 3.3f) / 4095.0f;

    char details[128];
    snprintf(details, sizeof(details), "Ext ADC Avg: %u, Voltage: %.3fV", avg, voltage);

    /* Just verify it reads something reasonable (0-3.3V) */
    if (voltage >= 0.0f && voltage <= 3.3f) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, avg);
    test_result_add_measurement(result, (uint32_t)(voltage * 1000));

    return 0;
}

/* ADC test suite */
const struct test_case adc_tests[] = {
    {
        .name = "adc_internal_temp",
        .description = "Read internal temperature sensor via ADC",
        .func = test_adc_internal_temp,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_ADC,
    },
    {
        .name = "adc_vref",
        .description = "Read internal voltage reference via ADC",
        .func = test_adc_vref,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_ADC,
    },
    {
        .name = "adc_external",
        .description = "Read external ADC channel (pin PA0)",
        .func = test_adc_external,
        .timeout_ms = 2000,
        .required_peripherals = PERIPH_ADC,
    },
    { .name = NULL, .func = NULL, .timeout_ms = 0, .required_peripherals = 0 }  /* Sentinel */
};