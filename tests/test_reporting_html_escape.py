import json
from pathlib import Path

from mcu_diagnostic_agent.reporting.generator import (
    DiagnosticReport,
    ReportGenerator,
    SuiteResultData,
    TestResultData,
)


def build_report() -> DiagnosticReport:
    test = TestResultData(
        name='<script>alert("test")</script>',
        suite="Safety & validation",
        status="pass",
        duration_ms=12.5,
        details='Device said <img src=x onerror="alert(1)"> — measured Δ=0.2V',
        measurements=[0.2],
        timestamp=1_800_000_000.0,
    )
    suite = SuiteResultData(
        name='<svg onload="alert(1)">',
        tests=[test],
        passed=1,
        failed=0,
        skipped=0,
        duration_ms=12.5,
    )
    return DiagnosticReport(
        mcu_family="arduino",
        mcu_part="ATmega328P — Uno R3",
        test_suites=["GPIO & ADC"],
        suites=[suite],
    )


def test_html_report_escapes_untrusted_dynamic_text(tmp_path: Path):
    report = build_report()
    generator = ReportGenerator(tmp_path)

    html = generator._build_html(report)

    assert "<script>alert" not in html
    assert "<svg onload=" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;svg onload=" in html
    assert "&lt;img src=x" in html
    assert "Δ=0.2V" in html


def test_report_files_are_written_as_utf8_and_include_unicode(tmp_path: Path):
    report = build_report()
    generator = ReportGenerator(tmp_path)

    text_path = generator.generate(report)

    assert text_path.is_file()
    assert Path(report.html_path).is_file()
    assert Path(report.json_path).is_file()
    payload = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    assert payload["json_path"] == report.json_path
    assert payload["html_path"] == report.html_path
    assert payload["report_path"] == report.report_path
    assert "ATmega328P — Uno R3" in Path(report.html_path).read_text(encoding="utf-8")
    assert "ATmega328P — Uno R3" in text_path.read_text(encoding="utf-8")
