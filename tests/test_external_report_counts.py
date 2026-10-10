from mcu_diagnostic_agent.reporting.generator import DiagnosticReport


def test_external_peripheral_outcomes_are_counted_separately():
    report = DiagnosticReport(
        mcu_family="stm32",
        mcu_part="STM32F407VG",
        test_suites=["basic"],
        external_peripherals=[
            {"name": "OLED", "status": "fail"},
            {"name": "sensor", "status": "pass"},
            {"name": "relay", "status": "warning"},
            {"name": "USB device", "status": "not_tested"},
            {"name": "unknown device", "status": "unknown"},
        ],
    )

    assert report.external_passed == 1
    assert report.external_failed == 1
    assert report.external_warnings == 1
    assert report.external_unknown == 2
    # Internal test totals remain separate from externally recorded observations.
    assert report.total_tests == 0
    assert report.failed == 0
