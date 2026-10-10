"""
MCU Diagnostic Agent - Host Orchestrator

Main application that coordinates probing, flashing, test execution,
and result reporting for MCU diagnostics.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict, dataclass, field
from enum import Enum
import time
import json
import yaml

from ..probe import get_probe, ProbeFactory, ProbeInterfaceType
from ..config import load_mcu_config, get_family_config
from ..firmware import FirmwareBuilder, FirmwareConfig
from .test_runner import TestRunner
from ..reporting import ReportGenerator, DiagnosticReport
from ..reporting.generator import SuiteResultData, TestResultData
from ..ai_diagnosis import generate_ai_analysis
from ..peripheral_observations import load_external_observations

logger = logging.getLogger(__name__)


class DiagnosticState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    FLASHING = "flashing"
    RUNNING_TESTS = "running_tests"
    COLLECTING_RESULTS = "collecting_results"
    GENERATING_REPORT = "generating_report"
    CLEANING_UP = "cleaning_up"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class DiagnosticConfig:
    """Configuration for a diagnostic session."""
    mcu_family: str
    mcu_part: Optional[str] = None
    probe_id: Optional[str] = None
    interface: ProbeInterfaceType = ProbeInterfaceType.SWD
    freq_khz: int = 1000
    test_suites: List[str] = field(default_factory=lambda: ["basic"])
    firmware_path: Optional[Path] = None
    output_dir: Path = Path("./results")
    keep_firmware: bool = False
    verbose: bool = False
    timeout: int = 300  # seconds
    ai_analysis: bool = False
    external_observations_file: Optional[Path] = None
    nemotron_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    allow_firmware_overwrite: bool = False


@dataclass
class DiagnosticSession:
    """Active diagnostic session state."""
    config: DiagnosticConfig
    state: DiagnosticState = DiagnosticState.IDLE
    probe: Any = None
    test_runner: Any = None
    report: Optional[DiagnosticReport] = None
    start_time: float = 0.0
    error: Optional[str] = None


class DiagnosticAgent:
    """Main diagnostic agent orchestrator."""

    def __init__(self, config: DiagnosticConfig):
        self.config = config
        self.session = DiagnosticSession(config=config)
        self.factory = ProbeFactory()
        self.firmware_builder = FirmwareBuilder()
        self.report_generator = ReportGenerator(config.output_dir)
        # Validate any supplied external evidence before connecting or flashing hardware.
        self.external_observations = load_external_observations(
            config.external_observations_file
        )
        self.firmware_overwritten = False

    async def run(self) -> DiagnosticReport:
        """Run complete diagnostic session."""
        self.session.start_time = time.time()
        self.session.state = DiagnosticState.CONNECTING

        try:
            # Step 1: Connect to target
            await self._connect()

            # Step 2: Build/flash test firmware
            await self._flash_firmware()

            # Step 3: Run tests
            await self._run_tests()

            # Step 4: Collect and process results
            await self._collect_results()

            # Step 5: Generate report
            await self._generate_report()

            # Step 6: Disconnect and leave target flash intact
            await self._cleanup()

            self.session.state = DiagnosticState.COMPLETE
            return self.session.report

        except Exception as e:
            self.session.state = DiagnosticState.ERROR
            self.session.error = str(e)
            logger.error(f"Diagnostic failed: {e}")
            await self._cleanup()
            raise

    async def _connect(self) -> None:
        """Connect to target MCU via debug probe."""
        logger.info(f"Connecting to {self.config.mcu_family} via {self.config.probe_id or 'auto'}...")

        self.session.probe = self.factory.create_probe(
            mcu_family=self.config.mcu_family,
            probe_id=self.config.probe_id,
            interface=self.config.interface,
            freq_khz=self.config.freq_khz
        )

        target_info = self.session.probe.connect()
        logger.info(f"Connected to {target_info.part_number} ({target_info.flash_size_kb}KB flash, {target_info.ram_size_kb}KB RAM)")

        # Identify specific part if not provided
        if not self.config.mcu_part:
            self.config.mcu_part = target_info.part_number

    async def _flash_firmware(self) -> None:
        """Build and flash diagnostic firmware."""
        if not self.config.allow_firmware_overwrite:
            raise RuntimeError(
                "Safety stop: diagnostic firmware overwrites the target's existing program, "
                "and automatic firmware backup/restore is not implemented. Re-run with "
                "--allow-firmware-overwrite only if you have a recovery method and accept "
                "that the diagnostic firmware will remain on the target."
            )
        self.session.state = DiagnosticState.FLASHING

        if self.config.firmware_path:
            firmware_path = Path(self.config.firmware_path)
            if not firmware_path.exists():
                raise FileNotFoundError(f"Firmware not found: {firmware_path}")
            logger.info(f"Using pre-built firmware: {firmware_path}")
        else:
            logger.info("Building diagnostic firmware...")
            firmware_config = FirmwareConfig(
                mcu_family=self.config.mcu_family,
                mcu_part=self.config.mcu_part,
                test_suites=self.config.test_suites,
            )

            build_result = await self.firmware_builder.build(firmware_config)
            if not build_result.success:
                raise RuntimeError(f"Firmware build failed: {build_result.error}")

            firmware_path = build_result.firmware_path
            logger.info(f"Firmware built: {firmware_path}")

        logger.info("Flashing firmware to target...")
        result = self.session.probe.flash_binary(firmware_path, verify=True)
        if not result.success:
            raise RuntimeError(f"Flash failed: {result.error}")

        logger.info(f"Flashed {result.bytes_written} bytes in {result.duration_ms:.1f}ms")
        self.firmware_overwritten = True

        # Reset and let firmware run
        self.session.probe.reset(halt=False, run=True)
        await asyncio.sleep(2)  # Wait for firmware to start

    async def _run_tests(self) -> None:
        """Run diagnostic tests via serial communication."""
        self.session.state = DiagnosticState.RUNNING_TESTS

        logger.info("Starting test execution...")
        self.session.test_runner = TestRunner(
            probe=self.session.probe,
            test_suites=self.config.test_suites,
            timeout=self.config.timeout
        )

        await self.session.test_runner.run()
        logger.info("Test execution complete")

    async def _collect_results(self) -> None:
        """Collect test results from target."""
        self.session.state = DiagnosticState.COLLECTING_RESULTS

        logger.info("Collecting results...")
        results = await self.session.test_runner.get_results()

        # Map runner output to the serializable report dataclasses.
        suite_data = [
            SuiteResultData(
                name=suite.name,
                tests=[
                    TestResultData(
                        name=test.name,
                        suite=test.suite,
                        status=test.status.value,
                        duration_ms=test.duration_ms,
                        details=test.details,
                        measurements=list(test.measurements),
                        timestamp=test.timestamp,
                    )
                    for test in suite.tests
                ],
                passed=suite.passed,
                failed=suite.failed,
                skipped=suite.skipped,
                duration_ms=suite.duration_ms,
            )
            for suite in results
        ]
        external = self.external_observations

        # Create report object.
        self.session.report = DiagnosticReport(
            mcu_family=self.config.mcu_family,
            mcu_part=self.config.mcu_part or "unknown",
            test_suites=list(self.config.test_suites),
            suites=suite_data,
            external_peripherals=external,
            duration=time.time() - self.session.start_time,
        )

        logger.info(f"Collected {sum(len(s.tests) for s in results)} test results")

    async def _generate_report(self) -> None:
        """Run optional evidence-based AI analysis and generate all reports."""
        self.session.state = DiagnosticState.GENERATING_REPORT
        report = self.session.report

        if self.config.ai_analysis:
            logger.info("Running Nemotron evidence analysis...")
            try:
                report.ai_analysis = generate_ai_analysis(
                    asdict(report),
                    model=self.config.nemotron_model,
                )
            except Exception as exc:
                # Preserve the measured diagnostic report even if the API is unavailable.
                report.ai_analysis = (
                    "AI analysis unavailable. No AI-generated cause or repair advice was "
                    f"produced. Reason: {type(exc).__name__}: {exc}"
                )
                logger.warning("Nemotron analysis unavailable: %s", exc)

        logger.info("Generating report...")
        report_path = self.report_generator.generate(report)
        logger.info(f"Report saved to {report_path}")

    async def _cleanup(self) -> None:
        """Disconnect safely without erasing user flash."""
        self.session.state = DiagnosticState.CLEANING_UP

        if self.session.probe and self.session.probe.connected:
            if self.firmware_overwritten and not self.config.keep_firmware:
                logger.warning(
                    "Original firmware backup/restore is not implemented. Diagnostic firmware "
                    "will remain on the target; restore your application using a known-good "
                    "board recovery procedure."
                )
            elif self.firmware_overwritten:
                logger.info("Leaving diagnostic firmware on target as requested.")
            logger.info("Disconnecting...")
            self.session.probe.disconnect()


async def main_async(args: argparse.Namespace) -> int:
    """Async main entry point."""
    config = DiagnosticConfig(
        mcu_family=args.family,
        mcu_part=args.part,
        probe_id=args.probe,
        interface=ProbeInterfaceType(args.interface),
        freq_khz=args.freq,
        test_suites=args.suites.split(",") if args.suites else ["basic"],
        firmware_path=Path(args.firmware) if args.firmware else None,
        output_dir=Path(args.output),
        keep_firmware=args.keep_firmware,
        verbose=args.verbose,
        timeout=args.timeout,
        ai_analysis=args.ai_analysis,
        external_observations_file=(
            Path(args.external_observations) if args.external_observations else None
        ),
        nemotron_model=args.nemotron_model,
        allow_firmware_overwrite=args.allow_firmware_overwrite,
    )

    if config.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    agent = DiagnosticAgent(config)
    report = await agent.run()

    # Print summary
    print(f"\n=== Diagnostic Complete ===")
    print(f"MCU: {report.mcu_family} {report.mcu_part}")
    print(f"Duration: {report.duration:.1f}s")
    print(f"Tests: {report.total_tests} ({report.passed} passed, {report.failed} failed, {report.skipped} skipped)")
    print(f"Report: {report.report_path}")

    return 0 if report.failed == 0 else 1


def main() -> int:
    """Synchronous main entry point."""
    parser = argparse.ArgumentParser(description="MCU Diagnostic Agent")
    parser.add_argument("family", choices=["stm32", "esp32", "rp2040", "arduino"],
                        help="MCU family")
    parser.add_argument("--part", help="Specific MCU part number")
    parser.add_argument("--probe", help="Debug probe ID (auto-detect if not specified)")
    parser.add_argument("--interface", choices=["swd", "jtag", "uart"], default="swd",
                        help="Debug interface")
    parser.add_argument("--freq", type=int, default=1000, help="Debug frequency (kHz)")
    parser.add_argument("--suites", help="Comma-separated test suites to run")
    parser.add_argument("--firmware", help="Pre-built firmware path (skip build)")
    parser.add_argument("--output", default="./results", help="Output directory")
    parser.add_argument("--keep-firmware", action="store_true",
                        help="Leave test firmware on device after test")
    parser.add_argument("--timeout", type=int, default=300, help="Test timeout (seconds)")
    parser.add_argument(
        "--ai-analysis",
        action="store_true",
        help="Add NVIDIA Nemotron root-cause, prevention, and repairability analysis to reports",
    )
    parser.add_argument(
        "--nemotron-model",
        default="nvidia/nemotron-3-ultra-550b-a55b",
        help="NVIDIA NIM model identifier (default: Nemotron 3 Ultra)",
    )
    parser.add_argument(
        "--external-observations",
        help="Path to JSON with observations/measurements from connected external peripherals",
    )
    parser.add_argument(
        "--allow-firmware-overwrite",
        action="store_true",
        help="Explicitly accept overwriting MCU firmware; no automatic backup/restore is available",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())