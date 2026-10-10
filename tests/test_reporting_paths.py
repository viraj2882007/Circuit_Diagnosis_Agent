import json

from mcu_diagnostic_agent.reporting.generator import (
    DiagnosticReport,
    ReportGenerator,
    SuiteResultData,
    TestResultData,
)


def test_report_generator_writes_utf8_and_populates_all_output_paths(tmp_path):
    test = TestResultData(
        name="known_device_id",
        suite="I2C",
        status="pass",
        duration_ms=3.0,
        details="Identified sensor μ with ID 0x60",
        measurements=[96.0],
        timestamp=1.0,
    )
    suite = SuiteResultData(
        name="I2C",
        tests=[test],
        passed=1,
        failed=0,
        skipped=0,
        duration_ms=3.0,
    )
    report = DiagnosticReport(
        mcu_family="arduino",
        mcu_part="Arduino Uno R3",
        test_suites=["i2c"],
        suites=[suite],
        ai_analysis="Verified ID: μ; status PASS.",
    )

    text_path = ReportGenerator(tmp_path).generate(report)

    assert text_path == tmp_path / text_path.name
    assert report.report_path == str(text_path)
    assert report.html_path.endswith(".html")
    assert report.json_path.endswith(".json")

    payload = json.loads(open(report.json_path, encoding="utf-8").read())
    assert payload["report_path"] == report.report_path
    assert payload["html_path"] == report.html_path
    assert payload["json_path"] == report.json_path

    html = open(report.html_path, encoding="utf-8").read()
    text = open(report.report_path, encoding="utf-8").read()
    assert "μ" in html
    assert "μ" in text
