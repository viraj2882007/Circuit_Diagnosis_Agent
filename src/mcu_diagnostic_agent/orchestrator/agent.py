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
from dataclasses import dataclass, field
from enum import Enum
import time
import json
import yaml

from ..probe import get_probe, ProbeFactory, ProbeInterfaceType
from ..config import load_mcu_config, get_family_config
from ..firmware import FirmwareBuilder, FirmwareConfig
from .test_runner import TestRunner, TestSession
from ..reporting import ReportGenerator, DiagnosticReport

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

            # Step 6: Cleanup (restore original firmware)
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

        # Create report object
        self.session.report = DiagnosticReport(
            mcu_family=self.config.mcu_family,
            mcu_part=self.config.mcu_part,
            test_suites=self.config.test_suites,
            results=results,
            duration=time.time() - self.session.start_time,
        )

        logger.info(f"Collected {sum(len(s.tests) for s in results)} test results")

    async def _generate_report(self) -> None:
        """Generate diagnostic report."""
        self.session.state = DiagnosticState.GENERATING_REPORT

        logger.info("Generating report...")
        report_path = self.report_generator.generate(self.session.report)
        logger.info(f"Report saved to {report_path}")

    async def _cleanup(self) -> None:
        """Cleanup: restore original firmware, disconnect."""
        self.session.state = DiagnosticState.CLEANING_UP

        if self.session.probe and self.session.probe.connected:
            if not self.config.keep_firmware:
                logger.info("Restoring original firmware...")
                # For now, just erase test firmware
                # TODO: Implement firmware backup/restore
                try:
                    self.session.probe.erase_flash()
                except Exception as e:
                    logger.warning(f"Failed to erase test firmware: {e}")

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