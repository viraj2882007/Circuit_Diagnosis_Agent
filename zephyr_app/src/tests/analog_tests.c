/**
 * Analog Tests - Combined ADC/DAC test suite
 */

#include "test_framework.h"

/* External test suite declarations */
extern const struct test_case adc_tests[];
extern const struct test_case dac_tests[];

/* Combined analog test suite */
const struct test_case analog_tests[] = {
    /* ADC tests */
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
    /* DAC tests */
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