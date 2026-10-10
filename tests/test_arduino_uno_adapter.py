from types import SimpleNamespace\n\nfrom mcu_diagnostic_agent import arduino_uno_adapter\nfrom mcu_diagnostic_agent.arduino_uno_adapter import (\n    _make_suite,\n    _test_result,\n    parse_adc_measurement,\n    parse_i2c_addresses,\n    parse_pair_results,\n)\nfrom mcu_diagnostic_agent.board_detection import detect_connected_boards


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



def test_parse_adc_measurement():
    assert parse_adc_measurement("ADC A0 expected LOW; average analogRead=3 / 1023 => PASS") == 3
    assert parse_adc_measurement("ADC A1 expected HIGH; average analogRead=1022 / 1023 => PASS") == 1022
    assert parse_adc_measurement("ERROR: Analog pin must be A0 through A5.") is None


def test_signature_failure_generates_report_and_skips_hardware_commands(tmp_path, monkeypatch):
    port = SimpleNamespace(
        device="COM9",
        description="Arduino Uno (COM9)",
        hwid="USB VID:PID=2341:0043",
        vid=0x2341,
        pid=0x0043,
        product="Arduino Uno",
        manufacturer="Arduino",
        serial_number="TEST",
    )
    detection = detect_connected_boards([port])[0]
    called = []

    def fake_signature(*args, **kwargs):
        return "fail", "Unexpected AVR signature", 4.2

    def fail_if_opened(*args, **kwargs):
        called.append(True)
        raise AssertionError("Serial port must not be opened after a failed signature check")

    monkeypatch.setattr(arduino_uno_adapter, "read_atmega328p_signature", fake_signature)
    monkeypatch.setattr(arduino_uno_adapter.serial, "Serial", fail_if_opened)

    report = arduino_uno_adapter.run_diagnostic(
        detection=detection,
        output_dir=tmp_path,
        interactive=True,
        check_signature=True,
    )

    assert called == []
    assert report.failed == 1
    assert report.skipped > 0
    assert report.json_path
    assert report.html_path
    assert report.report_path
