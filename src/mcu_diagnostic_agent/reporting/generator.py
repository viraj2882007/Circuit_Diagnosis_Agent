"""
Report Generator - Generates diagnostic reports in multiple formats.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import time

logger = logging.getLogger(__name__)


@dataclass
class TestResultData:
    """Serializable test result."""
    name: str
    suite: str
    status: str
    duration_ms: float
    details: str
    measurements: List[float]
    timestamp: float


@dataclass
class SuiteResultData:
    """Serializable suite result."""
    name: str
    tests: List[TestResultData]
    passed: int
    failed: int
    skipped: int
    duration_ms: float


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    mcu_family: str
    mcu_part: str
    test_suites: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration: float = 0.0
    firmware_version: int = 1
    device_id: str = ""
    suites: List[SuiteResultData] = field(default_factory=list)

    # Computed totals
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    # Output paths
    report_path: str = ""
    json_path: str = ""
    html_path: str = ""

    def __post_init__(self):
        self._compute_totals()

    def _compute_totals(self):
        """Compute aggregate totals."""
        self.total_tests = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0

        for suite in self.suites:
            self.total_tests += len(suite.tests)
            self.passed += suite.passed
            self.failed += suite.failed
            self.skipped += suite.skipped


class ReportGenerator:
    """Generates diagnostic reports in multiple formats."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, report: DiagnosticReport) -> Path:
        """Generate all report formats."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"diag_{report.mcu_family}_{report.mcu_part}_{timestamp}"

        # Generate JSON
        json_path = self.output_dir / f"{base_name}.json"
        self._generate_json(report, json_path)
        report.json_path = str(json_path)

        # Generate HTML
        html_path = self.output_dir / f"{base_name}.html"
        self._generate_html(report, html_path)
        report.html_path = str(html_path)

        # Generate summary text
        txt_path = self.output_dir / f"{base_name}.txt"
        self._generate_text(report, txt_path)
        report.report_path = str(txt_path)

        logger.info(f"Reports generated: {json_path}, {html_path}, {txt_path}")
        return txt_path

    def _generate_json(self, report: DiagnosticReport, path: Path) -> None:
        """Generate JSON report."""
        data = asdict(report)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_html(self, report: DiagnosticReport, path: Path) -> None:
        """Generate HTML report."""
        html = self._build_html(report)
        with open(path, 'w') as f:
            f.write(html)

    def _build_html(self, report: DiagnosticReport) -> str:
        """Build HTML report content."""
        status_colors = {
            'pass': '#28a745',
            'fail': '#dc3545',
            'skip': '#ffc107',
            'error': '#6c757d',
        }

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>MCU Diagnostic Report - {report.mcu_family} {report.mcu_part}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
        .stat {{ padding: 20px; border-radius: 8px; text-align: center; }}
        .stat.pass {{ background: #d4edda; color: #155724; }}
        .stat.fail {{ background: #f8d7da; color: #721c24; }}
        .stat.skip {{ background: #fff3cd; color: #856404; }}
        .stat.total {{ background: #d1ecf1; color: #0c5460; }}
        .stat h3 {{ margin: 0; font-size: 2em; }}
        .stat p {{ margin: 5px 0 0; }}
        .suite {{ margin-bottom: 30px; }}
        .suite h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
        .test {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }}
        .test:last-child {{ border-bottom: none; }}
        .test-name {{ font-family: monospace; }}
        .test-status {{ padding: 4px 12px; border-radius: 4px; color: white; font-weight: bold; }}
        .test-details {{ color: #666; font-size: 0.9em; margin-top: 4px; }}
        .measurements {{ color: #999; font-size: 0.8em; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MCU Diagnostic Report</h1>
        <p><strong>MCU:</strong> {report.mcu_family} {report.mcu_part}</p>
        <p><strong>Date:</strong> {report.timestamp}</p>
        <p><strong>Duration:</strong> {report.duration:.1f}s</p>
        <p><strong>Firmware Version:</strong> {report.firmware_version}</p>
        <p><strong>Device ID:</strong> {report.device_id}</p>
        <p><strong>Test Suites:</strong> {', '.join(report.test_suites)}</p>
    </div>

    <div class="summary">
        <div class="stat total">
            <h3>{report.total_tests}</h3>
            <p>Total Tests</p>
        </div>
        <div class="stat pass">
            <h3>{report.passed}</h3>
            <p>Passed</p>
        </div>
        <div class="stat fail">
            <h3>{report.failed}</h3>
            <p>Failed</p>
        </div>
        <div class="stat skip">
            <h3>{report.skipped}</h3>
            <p>Skipped</p>
        </div>
    </div>
"""

        for suite in report.suites:
            html += f"""
    <div class="suite">
        <h2>{suite.name} ({suite.passed} passed, {suite.failed} failed, {suite.skipped} skipped)</h2>
"""

            for test in suite.tests:
                color = status_colors.get(test.status, '#6c757d')
                meas_str = ', '.join(f'{m:.2f}' for m in test.measurements) if test.measurements else ''

                html += f"""
        <div class="test">
            <div>
                <div class="test-name">{test.name}</div>
                <div class="test-details">{test.details}</div>
                {f'<div class="measurements">Measurements: {meas_str}</div>' if meas_str else ''}
            </div>
            <div class="test-status" style="background: {color};">{test.status.upper()}</div>
        </div>
"""

            html += "</div>"

        html += """
</body>
</html>
"""
        return html

    def _generate_text(self, report: DiagnosticReport, path: Path) -> None:
        """Generate text summary report."""
        with open(path, 'w') as f:
            f.write(f"MCU Diagnostic Report\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"MCU: {report.mcu_family} {report.mcu_part}\n")
            f.write(f"Date: {report.timestamp}\n")
            f.write(f"Duration: {report.duration:.1f}s\n")
            f.write(f"Firmware Version: {report.firmware_version}\n")
            f.write(f"Device ID: {report.device_id}\n")
            f.write(f"Test Suites: {', '.join(report.test_suites)}\n\n")

            f.write(f"SUMMARY\n")
            f.write(f"{'-'*50}\n")
            f.write(f"Total Tests: {report.total_tests}\n")
            f.write(f"Passed:      {report.passed}\n")
            f.write(f"Failed:      {report.failed}\n")
            f.write(f"Skipped:     {report.skipped}\n\n")

            for suite in report.suites:
                f.write(f"\nSuite: {suite.name}\n")
                f.write(f"  Passed: {suite.passed}, Failed: {suite.failed}, Skipped: {suite.skipped}\n")
                f.write(f"  Duration: {suite.duration_ms:.1f}ms\n")

                for test in suite.tests:
                    status_str = test.status.upper()
                    f.write(f"  [{status_str}] {test.name}")
                    if test.details:
                        f.write(f" - {test.details}")
                    if test.measurements:
                        meas_str = ', '.join(f'{m:.2f}' for m in test.measurements)
                        f.write(f" (Measurements: {meas_str})")
                    f.write(f"\n")

            if report.failed > 0:
                f.write(f"\n{'!'*50}\n")
                f.write(f"FAILED TESTS DETECTED - Hardware may be defective\n")
                f.write(f"{'!'*50}\n")