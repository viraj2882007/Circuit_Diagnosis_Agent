"""
Test Runner - Executes tests on target MCU and collects results via serial.
"""

import asyncio
import logging
import re
import json
import serial
import serial.tools.list_ports
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time

from ..probe.base import ProbeInterface

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    suite: str
    status: TestStatus
    duration_ms: float
    details: str = ""
    measurements: List[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SuiteResult:
    """Test suite result."""
    name: str
    tests: List[TestResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: float = 0.0


class TestRunner:
    """Runs diagnostic tests on target and collects results."""

    def __init__(self, probe: ProbeInterface, test_suites: List[str],
                 timeout: int = 300, serial_port: Optional[str] = None,
                 baud_rate: int = 115200):
        self.probe = probe
        self.test_suites = test_suites
        self.timeout = timeout
        self.serial_port = serial_port
        self.baud_rate = baud_rate

        self.suites: List[SuiteResult] = []
        self.current_suite: Optional[SuiteResult] = None
        self._running = False
        self._serial_reader: Optional[asyncio.Task] = None
        self._serial: Optional[serial.Serial] = None
        self._results_buffer: List[TestResult] = []

    async def run(self) -> List[SuiteResult]:
        """Run all test suites."""
        self._running = True
        self.suites = []
        self._results_buffer = []

        # Start serial monitoring
        await self._start_serial_monitor()

        # Wait for firmware to be ready
        await asyncio.sleep(2)

        # Send command to run tests
        await self._send_command("diag run all")

        # Wait for completion
        start_time = time.time()
        while self._running and (time.time() - start_time) < self.timeout:
            await asyncio.sleep(0.5)

        await self._stop_serial_monitor()

        if self._running:
            logger.warning("Test timeout")
            self._running = False

        return self.suites

    async def _start_serial_monitor(self) -> None:
        """Start monitoring serial output from target."""
        # Find serial port if not specified
        if not self.serial_port:
            self.serial_port = self._find_serial_port()
            if not self.serial_port:
                logger.warning("No serial port found for test monitoring")

        if self.serial_port:
            try:
                self._serial = serial.Serial(
                    port=self.serial_port,
                    baudrate=self.baud_rate,
                    timeout=0.1
                )
                logger.info(f"Opened serial port {self.serial_port} at {self.baud_rate} baud")
            except Exception as e:
                logger.error(f"Failed to open serial port {self.serial_port}: {e}")
                self._serial = None

        self._serial_reader = asyncio.create_task(self._serial_read_loop())

    def _find_serial_port(self) -> Optional[str]:
        """Auto-detect serial port for target."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Common patterns for debug probes with CDC/serial
            if any(vid_pid in port.hwid.upper() for vid_pid in [
                "0483:3748", "0483:374B",  # ST-Link
                "1366:0101", "1366:0105",  # J-Link
                "1D50:6018",               # Black Magic Probe
                "2E8A:0005",               # PicoProbe
            ]):
                return port.device
            # Also check for generic USB CDC
            if "CDC" in port.description or "ACM" in port.description:
                return port.device
        return None

    async def _stop_serial_monitor(self) -> None:
        """Stop serial monitoring."""
        if self._serial_reader:
            self._serial_reader.cancel()
            try:
                await self._serial_reader
            except asyncio.CancelledError:
                pass

        if self._serial and self._serial.is_open:
            self._serial.close()

    async def _serial_read_loop(self) -> None:
        """Read loop for serial data."""
        buffer = ""
        while self._running:
            try:
                if self._serial and self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self._parse_output(line.strip())

                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Serial read error: {e}")
                await asyncio.sleep(0.1)

    def _parse_output(self, line: str) -> None:
        """Parse test output from target."""
        if not line:
            return

        # Parse binary report packets (starting with DIAG magic)
        if line.startswith('> '):
            self._parse_report_line(line[2:])
        elif line.startswith('{'):
            self._parse_json_report(line)
        elif '=== DIAGNOSTIC SUMMARY ===' in line:
            self._running = False
        elif line.startswith('TEST:') or line.startswith('SUITE:'):
            # Human-readable format from firmware
            self._parse_text_report(line)

    def _parse_report_line(self, line: str) -> None:
        """Parse text report line."""
        # Format: > XX message
        parts = line.split(' ', 1)
        if len(parts) < 2:
            return

        status_hex = parts[0]
        message = parts[1] if len(parts) > 1 else ""

        try:
            status = int(status_hex, 16)
        except ValueError:
            return

        if status == 0x00:  # RESP_OK
            self._handle_test_result(message)
        elif status == 0xFF:  # RESP_ERROR
            logger.error(f"Target error: {message}")

    def _parse_json_report(self, line: str) -> None:
        """Parse JSON report from target."""
        try:
            report = json.loads(line)
            if report.get('type') == 'test_result':
                self._handle_test_result_json(report)
            elif report.get('type') == 'suite_summary':
                self._handle_suite_summary(report)
            elif report.get('type') == 'final_report':
                self._running = False
        except json.JSONDecodeError:
            pass

    def _parse_text_report(self, line: str) -> None:
        """Parse human-readable text report."""
        # Format: TEST: name: PASS/FAIL - details
        # Format: SUITE: name: passed=X failed=Y skipped=Z
        if line.startswith('TEST:'):
            match = re.match(r'TEST:\s*(\w+):\s*(PASS|FAIL|SKIP)\s*-\s*(.*)', line)
            if match:
                name, status_str, details = match.groups()
                status = TestStatus(status_str.lower())
                result = TestResult(
                    name=name,
                    suite=self.current_suite.name if self.current_suite else "unknown",
                    status=status,
                    duration_ms=0,
                    details=details,
                )
                self._add_result(result)
        elif line.startswith('SUITE:'):
            match = re.match(r'SUITE:\s*(\w+):\s*passed=(\d+)\s*failed=(\d+)\s*skipped=(\d+)', line)
            if match:
                name, passed, failed, skipped = match.groups()
                if self.current_suite:
                    self.suites.append(self.current_suite)
                self.current_suite = SuiteResult(
                    name=name,
                    passed=int(passed),
                    failed=int(failed),
                    skipped=int(skipped),
                )

    def _handle_test_result(self, message: str) -> None:
        """Handle test result message."""
        # Format: "test_name: PASS/FAIL - details"
        match = re.match(r'(\w+):\s*(PASS|FAIL|SKIP)\s*-\s*(.*)', message)
        if not match:
            return

        name, status_str, details = match.groups()
        status = TestStatus(status_str.lower())

        result = TestResult(
            name=name,
            suite=self.current_suite.name if self.current_suite else "unknown",
            status=status,
            duration_ms=0,
            details=details,
        )

        self._add_result(result)

    def _handle_test_result_json(self, report: Dict) -> None:
        """Handle JSON test result."""
        result = TestResult(
            name=report.get('name', 'unknown'),
            suite=report.get('suite', 'unknown'),
            status=TestStatus(report.get('status', 'error')),
            duration_ms=report.get('duration_ms', 0),
            details=report.get('details', ''),
            measurements=report.get('measurements', []),
        )
        self._add_result(result)

    def _handle_suite_summary(self, report: Dict) -> None:
        """Handle suite summary."""
        if self.current_suite:
            self.suites.append(self.current_suite)

        self.current_suite = SuiteResult(
            name=report.get('suite_name', 'unknown'),
            passed=report.get('passed', 0),
            failed=report.get('failed', 0),
            skipped=report.get('skipped', 0),
            duration_ms=report.get('duration_ms', 0),
        )

    def _add_result(self, result: TestResult) -> None:
        """Add test result to current suite."""
        if self.current_suite:
            self.current_suite.tests.append(result)
            if result.status == TestStatus.PASS:
                self.current_suite.passed += 1
            elif result.status == TestStatus.FAIL:
                self.current_suite.failed += 1
            elif result.status == TestStatus.SKIP:
                self.current_suite.skipped += 1

    async def _send_command(self, cmd: str) -> None:
        """Send command to target via serial."""
        logger.debug(f"Sending command: {cmd}")
        if self._serial and self._serial.is_open:
            self._serial.write((cmd + '\n').encode())

    async def get_results(self) -> List[SuiteResult]:
        """Get collected test results."""
        # Add any remaining suite
        if self.current_suite and self.current_suite not in self.suites:
            self.suites.append(self.current_suite)
        return self.suites


class SerialTestRunner(TestRunner):
    """Test runner using actual serial port."""

    def __init__(self, *args, serial_port: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.serial_port = serial_port

    async def _start_serial_monitor(self) -> None:
        """Open serial port and start monitoring."""
        try:
            self._serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=0.1
            )
            logger.info(f"Opened serial port {self.serial_port}")
        except Exception as e:
            logger.error(f"Failed to open serial port: {e}")
            raise

        self._serial_reader = asyncio.create_task(self._serial_read_loop())

    async def _send_command(self, cmd: str) -> None:
        """Send command via serial."""
        if self._serial and self._serial.is_open:
            self._serial.write((cmd + '\n').encode())

    async def _stop_serial_monitor(self) -> None:
        """Close serial port."""
        await super()._stop_serial_monitor()
        if self._serial and self._serial.is_open:
            self._serial.close()