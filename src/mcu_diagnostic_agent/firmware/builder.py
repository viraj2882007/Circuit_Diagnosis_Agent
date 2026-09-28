"""
Firmware Builder - Builds Zephyr-based diagnostic firmware for target MCUs.
"""

import asyncio
import logging
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FirmwareConfig:
    """Configuration for firmware build."""
    mcu_family: str
    mcu_part: str
    test_suites: List[str] = field(default_factory=lambda: ["basic"])
    zephyr_base: Optional[Path] = None
    build_dir: Optional[Path] = None
    extra_cmake_args: List[str] = field(default_factory=list)


@dataclass
class BuildResult:
    """Result of firmware build."""
    success: bool
    firmware_path: Optional[Path] = None
    build_dir: Optional[Path] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    size_bytes: int = 0
    size_flash_kb: float = 0.0
    size_ram_kb: float = 0.0


class FirmwareBuilder:
    """Builds diagnostic firmware using Zephyr RTOS."""

    # MCU family to Zephyr board mapping
    BOARD_MAP = {
        "stm32": {
            "STM32F030R8": "nucleo_f030r8",
            "STM32F072RB": "nucleo_f072rb",
            "STM32F103C8": "nucleo_f103rb",
            "STM32F103RB": "nucleo_f103rb",
            "STM32F303RE": "nucleo_f303re",
            "STM32F401RE": "nucleo_f401re",
            "STM32F407VG": "nucleo_f407zg",
            "STM32F411CE": "nucleo_f411re",
            "STM32F429ZI": "nucleo_f429zi",
            "STM32F746ZG": "nucleo_f746zg",
            "STM32G031K8": "nucleo_g031k8",
            "STM32G071RB": "nucleo_g071rb",
            "STM32G431KB": "nucleo_g431rb",
            "STM32G474RE": "nucleo_g474re",
            "STM32H743ZI": "nucleo_h743zi",
            "STM32L053R8": "nucleo_l053r8",
            "STM32L152RE": "nucleo_l152re",
            "STM32L432KC": "nucleo_l432kc",
            "STM32L476RG": "nucleo_l476rg",
            "STM32L552ZE": "nucleo_l552ze",
            "STM32U575ZI": "nucleo_u575zi",
            "STM32WB55RG": "nucleo_wb55rg",
        },
        "esp32": {
            "ESP32": "esp32_devkitc",
            "ESP32S2": "esp32s2_devkitc",
            "ESP32S3": "esp32s3_devkitc",
            "ESP32C3": "esp32c3_devkitc",
            "ESP32H2": "esp32h2_devkitc",
        },
        "rp2040": {
            "RP2040": "rpi_pico",
        },
        "arduino": {
            "ATMEGA328P": "arduino_uno",
            "ATMEGA2560": "arduino_mega",
            "ATSAMD21G18": "arduino_zero",
            "ATSAMD51J19": "arduino_nano_33_iot",
            "ATSAMD21E18": "arduino_mkr_zero",
        },
    }

    def __init__(self, zephyr_base: Optional[Path] = None, west_cmd: str = "west"):
        self.zephyr_base = zephyr_base or Path.cwd() / "zephyr"
        self.west_cmd = west_cmd
        self.app_dir = Path(__file__).parent.parent.parent / "zephyr_app"

    def get_board(self, family: str, part: str) -> str:
        """Get Zephyr board name for MCU."""
        return self.BOARD_MAP.get(family, {}).get(part.upper(), "unknown")

    async def build(self, config: FirmwareConfig) -> BuildResult:
        """Build firmware for target MCU."""
        start_time = time.time()

        board = self.get_board(config.mcu_family, config.mcu_part)
        if board == "unknown":
            return BuildResult(
                success=False,
                error=f"No board mapping for {config.mcu_family} {config.mcu_part}",
                duration_ms=(time.time() - start_time) * 1000
            )

        # Determine build directory
        if config.build_dir:
            build_dir = config.build_dir
        else:
            build_dir = Path(tempfile.mkdtemp(prefix=f"diag_build_{config.mcu_family}_"))

        try:
            # Prepare CMake arguments
            cmake_args = [
                "-DBOARD=" + board,
                "-DCMAKE_BUILD_TYPE=Release",
            ]
            cmake_args.extend(config.extra_cmake_args)

            # Add test suite configuration
            if config.test_suites:
                suites_str = ";".join(config.test_suites)
                cmake_args.append(f"-DDIAGNOSTIC_TEST_SUITES={suites_str}")

            # Run west build
            logger.info(f"Building for {board} in {build_dir}")

            cmd = [
                self.west_cmd, "build",
                "-b", board,
                "--build-dir", str(build_dir),
                "--", *cmake_args,
                str(self.app_dir)
            ]

            logger.debug(f"Build command: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.zephyr_base if self.zephyr_base.exists() else None
            )

            stdout, stderr = await process.communicate()

            duration_ms = (time.time() - start_time) * 1000

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(f"Build failed: {error_msg}")
                return BuildResult(
                    success=False,
                    error=error_msg,
                    duration_ms=duration_ms
                )

            # Find output firmware
            firmware_path = self._find_firmware(build_dir, board)
            if not firmware_path:
                return BuildResult(
                    success=False,
                    error="Firmware not found after build",
                    duration_ms=duration_ms
                )

            # Get size info
            size_info = self._get_size_info(build_dir)

            logger.info(f"Build successful: {firmware_path} ({size_info['flash_kb']:.1f}KB flash, {size_info['ram_kb']:.1f}KB RAM)")

            return BuildResult(
                success=True,
                firmware_path=firmware_path,
                build_dir=build_dir,
                duration_ms=duration_ms,
                size_bytes=firmware_path.stat().st_size,
                size_flash_kb=size_info['flash_kb'],
                size_ram_kb=size_info['ram_kb'],
            )

        except Exception as e:
            return BuildResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )

    def _find_firmware(self, build_dir: Path, board: str) -> Optional[Path]:
        """Find built firmware file."""
        # Common output locations
        candidates = [
            build_dir / "zephyr" / "zephyr.bin",
            build_dir / "zephyr" / "zephyr.hex",
            build_dir / "zephyr" / "zephyr.elf",
            build_dir / "build" / "zephyr.bin",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Search recursively
        for ext in [".bin", ".hex", ".elf"]:
            files = list(build_dir.rglob(f"*{ext}"))
            if files:
                return files[0]

        return None

    def _get_size_info(self, build_dir: Path) -> Dict[str, float]:
        """Get firmware size information."""
        size_info = {"flash_kb": 0.0, "ram_kb": 0.0}

        # Try to run size command
        elf_files = list(build_dir.rglob("zephyr.elf"))
        if elf_files:
            try:
                result = subprocess.run(
                    ["arm-none-eabi-size", "-A", str(elf_files[0])],
                    capture_output=True, text=True, timeout=10
                )
                # Parse output for flash/ram sizes
                for line in result.stdout.split('\n'):
                    if '.text' in line or '.data' in line or '.rodata' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            size_info['flash_kb'] += int(parts[1]) / 1024
                    if '.bss' in line or '.data' in line or '.noinit' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            size_info['ram_kb'] += int(parts[1]) / 1024
            except Exception:
                pass

        return size_info

    def cleanup_build_dir(self, build_dir: Path) -> None:
        """Clean up build directory."""
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            logger.warning(f"Failed to clean build dir {build_dir}: {e}")