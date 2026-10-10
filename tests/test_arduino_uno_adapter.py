from mcu_diagnostic_agent.arduino_uno_adapter import _make_suite, _test_result, parse_i2c_addresses, parse_pair_results


def test_parse_pair_results_extracts_both_directions():
    lines = [
        "Testing jumper connection D2 <-> D3",
        "D2 output -> D3 input: LOW phase read=0, HIGH phase read=1 => PASS",
        "D3 output -> D2 input: LOW phase read=0, HIGH phase read=1 => FAIL",
        "PAIR RESULT: FAIL - check jumper and pins",
    ]

    results = parse_pair_results(lines)

    assert results == [
        (
            "D2 output -> D3 input",
            "pass",
            "D2 output -> D3 input: LOW phase read=0, HIGH phase read=1 => PASS",
        ),
        (
            "D3 output -> D2 input",
            "fail",
            "D3 output -> D2 input: LOW phase read=0, HIGH phase read=1 => FAIL",
        ),
    ]


def test_parse_i2c_addresses_deduplicates_and_ignores_non_results():
    lines = [
        "I2C_ADDR:0x3C",
        "I2C_ADDR:0x76",
        "I2C_ADDR:0x3C",
        "I2C_SCAN RESULT: 2 ADDRESS(ES) ACKNOWLEDGED; DEVICE HEALTH NOT VERIFIED",
        "I2C_ADDR:0x7FF",
    ]

    assert parse_i2c_addresses(lines) == [0x3C, 0x76]


def test_suite_counts_pass_fail_and_skip_without_guessing():
    tests = [
        _test_result("one", "GPIO", "pass", "measured pass"),
        _test_result("two", "GPIO", "fail", "measured fail"),
        _test_result("three", "GPIO", "skip", "not measured"),
    ]

    suite = _make_suite("GPIO", tests)

    assert suite.passed == 1
    assert suite.failed == 1
    assert suite.skipped == 1
