from pathlib import Path
from types import SimpleNamespace

from mcu_diagnostic_agent import arduino_uno_adapter
from mcu_diagnostic_agent.arduino_uno_adapter import (
    _make_suite,
    _test_result,
    parse_adc_measurement,
    parse_firmware_duration,
    parse_i2c_addresses,
    parse_pair_results,
    parse_pwm_measurements,
)
from mcu_diagnostic_agent.board_detection import detect_connected_boards


def test_startup_reader_drains_startup_before_handshake():
    class FakeSerial:
        def __init__(self):
            self.lines = [
                b"UNO R3 DIAGNOSTIC SKETCH READY\r\n",
                b"BOARD:ARDUINO_UNO_R3\r\n",
                b"FIRMWARE_VERSION:3\r\n",
                b"INFO RESULT: PASS\r\n",
                b"No external wires should be connected until a test asks for one.\r\n",
                b"LED test sequence complete. Did the onboard L LED blink 3 times?\r\n",
                b"NEXT COMMAND RESPONSE\r\n",
            ]

        def readline(self):
            return self.lines.pop(0) if self.lines else b""

    serial_port = FakeSerial()
    lines = arduino_uno_adapter._read_startup(serial_port, timeout_seconds=1.0)

    assert any("UNO R3 DIAGNOSTIC SKETCH READY" in line for line in lines)
    assert any("LED test sequence complete." in line for line in lines)
    assert serial_port.lines == [b"NEXT COMMAND RESPONSE\r\n"]


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


def test_parse_firmware_duration_uses_device_measured_value():
    assert parse_firmware_duration("D2 output -> D3 input: duration_ms=7 => PASS") == 7.0
    assert parse_firmware_duration("PWM RESULT: PASS; duration_ms=42") == 42.0
    assert parse_firmware_duration("ADC A0 expected LOW; no timing available") is None


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


def test_unknown_usb_bridge_requires_explicit_board_confirmation(monkeypatch):
    from mcu_diagnostic_agent import arduino_uno_adapter as adapter
    from mcu_diagnostic_agent.board_detection import BoardDetection

    unknown = BoardDetection(
        port="COM7",
        description="USB-SERIAL CH340",
        hwid="USB VID:PID=1A86:7523",
        vid=0x1A86,
        pid=0x7523,
        profile_id=None,
        candidate_profile_id=None,
        confidence="unknown",
        match_method="unrecognized",
        evidence=["Unmatched USB VID/PID 1A86:7523"],
    )
    monkeypatch.setattr(adapter, "detect_connected_boards", lambda: [unknown])

    try:
        adapter._choose_port("COM7")
    except RuntimeError as exc:
        assert "--confirm-board arduino_uno_r3" in str(exc)
    else:
        raise AssertionError("Unknown USB bridge must not be auto-selected")

    confirmed = adapter._choose_port("COM7", "arduino_uno_r3")
    assert confirmed.profile_id == "arduino_uno_r3"
    assert confirmed.match_method == "explicit_user_confirmation"
    assert confirmed.confidence == "user_confirmed"



def test_serial_port_error_generates_failure_report_and_marks_tests_skipped(tmp_path, monkeypatch):
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

    monkeypatch.setattr(
        arduino_uno_adapter,
        "read_atmega328p_signature",
        lambda *args, **kwargs: ("skip", "AVRDUDE not found", 0.0),
    )

    def raise_port_busy(*args, **kwargs):
        raise arduino_uno_adapter.serial.SerialException("port busy")

    monkeypatch.setattr(arduino_uno_adapter.serial, "Serial", raise_port_busy)

    report = arduino_uno_adapter.run_diagnostic(
        detection=detection,
        output_dir=tmp_path,
        interactive=True,
        check_signature=True,
    )

    assert report.failed == 1
    assert report.skipped >= 5
    assert "Serial connection to diagnostic firmware" in {
        test.name for suite in report.suites for test in suite.tests
    }
    assert Path(report.json_path).is_file()


def test_parse_pwm_measurements_extracts_frequency_and_duty_cycle():
    assert parse_pwm_measurements(
        "PWM_MEASUREMENT: high_us=1020 low_us=1020 frequency_hz=490.2 duty_percent=50.0"
    ) == [490.2, 50.0]
    assert parse_pwm_measurements("PWM_MEASUREMENT: unavailable") == []
