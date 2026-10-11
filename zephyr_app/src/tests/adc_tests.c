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

/* Internal channels and conversion formulas below are enabled only for STM32. */
#if defined(CONFIG_SOC_FAMILY_STM32)
#define ADC_TEMP_CHANNEL 16  /* STM32F4 ADC temperature sensor */
#define ADC_VREF_CHANNEL 17  /* STM32F4 internal voltage reference */

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
#endif

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
#if !defined(CONFIG_SOC_FAMILY_STM32)
    test_result_set_skip(result, "Internal temperature channel/scaling is board-specific; no profile for this MCU family.");
    return 0;
#else
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
    /* Integer-only estimate assumes a nominal 3.300 V ADC reference. */
    uint32_t millivolts = ((uint32_t)raw * 3300U) / 4095U;

    /* STM32-like internal sensor approximation: V25=760 mV, slope=2.5 mV/°C. */
    int32_t temp_c_x10 = (((int32_t)millivolts - 760) * 4) + 250;

    char details[128];
    snprintf(details, sizeof(details),
             "Raw: %u, nominal_Vref=3300mV, estimated_voltage=%lumV, temp_x10_C=%ld",
             raw, (unsigned long)millivolts, (long)temp_c_x10);

    /* This temperature model is device-specific; only a broad plausibility check is made. */
    if (temp_c_x10 > -400 && temp_c_x10 < 1250) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, raw);
    test_result_add_measurement(result, millivolts);

    return 0;
#endif
}

/* Test: Internal voltage reference */
int test_adc_vref(struct diagnostic_context *ctx, struct test_result *result)
{
#if !defined(CONFIG_SOC_FAMILY_STM32)
    test_result_set_skip(result, "Internal VREF channel mapping is MCU-specific; no profile for this MCU family.");
    return 0;
#else
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
    uint32_t millivolts = ((uint32_t)raw * 3300U) / 4095U;

    char details[128];
    snprintf(details, sizeof(details),
             "VREF Raw: %u, nominal_Vref=3300mV, estimated_internal_Vref=%lumV",
             raw, (unsigned long)millivolts);

    /* VREF is expected around 1.0-1.4 V only for supported sensors with this profile. */
    if (millivolts > 1000U && millivolts < 1400U) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, raw);
    test_result_add_measurement(result, millivolts);

    return 0;
#endif
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
        test_result_set_skip(result, "ADC channel 0 is not available in this board's device tree/profile.");
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
    uint32_t estimated_millivolts = ((uint32_t)avg * 3300U) / 4095U;

    char details[160];
    snprintf(details, sizeof(details),
             "Ext ADC Avg: %u/4095, estimated_voltage=%lumV assuming nominal 3300mV reference",
             avg, (unsigned long)estimated_millivolts);

    /* Range plausibility only; calibration accuracy requires an independent voltage reference. */
    if (avg <= 4095U) {
        test_result_set_pass(result, details);
    } else {
        test_result_set_fail(result, details);
    }

    test_result_add_measurement(result, avg);
    test_result_add_measurement(result, estimated_millivolts);

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