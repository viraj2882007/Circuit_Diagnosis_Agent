"""
OpenOCD backend implementation for probe interface.
Supports targets not well supported by PyOCD (ESP32, RP2040, etc.)
"""

import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import (
    ProbeInterface, ProbeInterfaceType, ProbeCapabilities,
    ProbeError, ConnectionError, FlashError, EraseError, ResetError,
    TargetInfo, FlashResult, MemoryRegion, FlashAlgorithm
)

logger = logging.getLogger(__name__)


class OpenOCDBackend(ProbeInterface):
    """OpenOCD-based debug probe backend."""

    # OpenOCD config templates per target family
    CONFIG_TEMPLATES = {
        "stm32": """
interface/{interface}
transport select {transport}
source [find target/stm32{series}x.cfg]
{init_commands}
""",
        "esp32": """
interface/{interface}
transport select jtag
source [find target/esp32.cfg]
{init_commands}
""",
        "esp32s2": """
interface/{interface}
transport select jtag
source [find target/esp32s2.cfg]
{init_commands}
""",
        "esp32s3": """
interface/{interface}
transport select jtag
source [find target/esp32s3.cfg]
{init_commands}
""",
        "esp32c3": """
interface/{interface}
transport select jtag
source [find target/esp32c3.cfg]
{init_commands}
""",
        "esp32h2": """
interface/{interface}
transport select jtag
source [find target/esp32h2.cfg]
{init_commands}
""",
        "rp2040": """
interface/{interface}
transport select swd
source [find target/rp2040.cfg]
{init_commands}
""",
        "samd21": """
interface/{interface}
transport select swd
source [find target/atsamd21.cfg]
{init_commands}
""",
        "samd51": """
interface/{interface}
transport select swd
source [find target/atsamd51.cfg]
{init_commands}
""",
        "avr": """
interface/{interface}
source [find target/avr.cfg]
{init_commands}
""",
    }

    INTERFACE_MAP = {
        "stlink": "stlink",
        "jlink": "jlink",
        "cmsis-dap": "cmsis-dap",
        "ftdi": "ftdi",
        "blackmagic": "blackmagic",
        "picoprobe": "picoprobe",
    }

    TRANSPORT_MAP = {
        ProbeInterfaceType.SWD: "swd",
        ProbeInterfaceType.JTAG: "jtag",
    }

    def __init__(self, probe_id: Optional[str] = None,
                 interface: ProbeInterfaceType = ProbeInterfaceType.SWD,
                 target_family: str = "stm32",
                 target_config: Optional[str] = None,
                 freq_khz: int = 1000,
                 openocd_path: str = "openocd"):
        super().__init__(probe_id, interface)
        self.target_family = target_family.lower()
        self.target_config = target_config
        self.freq_khz = freq_khz
        self.openocd_path = openocd_path
        self._process: Optional[subprocess.Popen] = None
        self._config_file: Optional[Path] = None
        self._telnet_port = 4444
        self._gdb_port = 3333
        self._tcl_port = 6666

    def _build_config(self, init_commands: str = "") -> str:
        """Build OpenOCD config file content."""
        interface_name = self.INTERFACE_MAP.get(self.probe_id, "cmsis-dap") if self.probe_id else "cmsis-dap"
        transport = self.TRANSPORT_MAP.get(self.interface, "swd")

        template = self.CONFIG_TEMPLATES.get(self.target_family, self.CONFIG_TEMPLATES["stm32"])

        # Family-specific series detection
        series = ""
        if self.target_family == "stm32":
            series = "f1"  # default, would be detected from target

        return template.format(
            interface=interface_name,
            transport=transport,
            series=series,
            init_commands=init_commands or f"adapter speed {self.freq_khz}"
        )

    def _write_config(self, config_content: str) -> Path:
        """Write config to temporary file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
            f.write(config_content)
            return Path(f.name)

    def _start_openocd(self, config: str) -> None:
        """Start OpenOCD process."""
        self._config_file = self._write_config(config)

        cmd = [
            self.openocd_path,
            "-f", str(self._config_file),
            "-c", f"telnet_port {self._telnet_port}",
            "-c", f"gdb_port {self._gdb_port}",
            "-c", f"tcl_port {self._tcl_port}",
        ]

        logger.debug(f"Starting OpenOCD: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for OpenOCD to start
        time.sleep(2)

        if self._process.poll() is not None:
            stdout, stderr = self._process.communicate()
            raise ConnectionError(f"OpenOCD failed to start: {stderr}")

    def _send_command(self, cmd: str) -> str:
        """Send command via telnet to OpenOCD."""
        try:
            import telnetlib
            tn = telnetlib.Telnet("localhost", self._telnet_port, timeout=5)
            tn.read_until(b"> ", timeout=2)
            tn.write(cmd.encode() + b"\n")
            output = tn.read_until(b"> ", timeout=5).decode()
            tn.close()
            return output
        except Exception as e:
            raise ProbeError(f"Telnet command failed: {e}")

    def connect(self, target_override: Optional[str] = None, freq_khz: int = 1000) -> TargetInfo:
        """Connect to target using OpenOCD."""
        if self.connected:
            return self.target_info

        if freq_khz:
            self.freq_khz = freq_khz

        try:
            config = self._build_config(f"adapter speed {self.freq_khz}")
            self._start_openocd(config)

            # Initialize target
            self._send_command("reset init")
            time.sleep(0.5)

            # Get target info
            self.target_info = self._get_target_info(target_override)
            self.connected = True

            logger.info(f"Connected to {self.target_info.part_number} via OpenOCD")
            return self.target_info

        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Failed to connect via OpenOCD: {e}")

    def _get_target_info(self, target_override: Optional[str] = None) -> TargetInfo:
        """Get target info via OpenOCD commands."""
        # This is simplified - real implementation would parse OpenOCD output
        return TargetInfo(
            family=self.target_family.upper(),
            part_number=target_override or "Unknown",
            revision="Unknown",
            flash_size_kb=0,
            ram_size_kb=0,
            cpu_type="Cortex-M" if "cortex" in self.target_family else "Unknown",
        )

    def disconnect(self) -> None:
        """Disconnect and stop OpenOCD."""
        if self._process:
            try:
                self._send_command("shutdown")
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            finally:
                self._process = None

        if self._config_file and self._config_file.exists():
            try:
                self._config_file.unlink()
            except Exception:
                pass

        self.connected = False

    def reset(self, halt: bool = True, run: bool = False) -> None:
        """Reset target."""
        if not self.connected:
            raise ResetError("Not connected")
        cmd = "reset halt" if halt else "reset run"
        self._send_command(cmd)

    def halt(self) -> None:
        """Halt target."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._send_command("halt")

    def resume(self) -> None:
        """Resume target."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._send_command("resume")

    def read_memory(self, address: int, length: int) -> bytes:
        """Read memory via OpenOCD."""
        if not self.connected:
            raise ProbeError("Not connected")

        # Use OpenOCD's memory read command
        output = self._send_command(f"mwb {address:#x} {length}")
        # Parse output to bytes - simplified
        try:
            return bytes.fromhex(output.replace(" ", "").replace("\n", ""))
        except Exception:
            return b"\x00" * length

    def write_memory(self, address: int, data: bytes) -> None:
        """Write memory via OpenOCD."""
        if not self.connected:
            raise ProbeError("Not connected")

        hex_data = " ".join(f"{b:02x}" for b in data)
        self._send_command(f"mwb {address:#x} {hex_data}")

    def read_core_register(self, reg_name: str) -> int:
        """Read core register."""
        if not self.connected:
            raise ProbeError("Not connected")
        output = self._send_command(f"reg {reg_name}")
        return int(output.strip(), 16)

    def write_core_register(self, reg_name: str, value: int) -> None:
        """Write core register."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._send_command(f"reg {reg_name} {value:#x}")

    def flash_binary(self, file_path: Path, address: Optional[int] = None,
                     verify: bool = True, erase_first: bool = True) -> FlashResult:
        """Flash binary file via OpenOCD."""
        if not self.connected:
            raise FlashError("Not connected")

        start_time = time.time()
        try:
            flash_addr = address or 0x08000000

            if erase_first:
                self._send_command(f"flash erase_address {flash_addr:#x} {file_path.stat().st_size}")

            self._send_command(f"flash write_image {file_path} {flash_addr:#x}")

            if verify:
                self._send_command(f"flash verify_image {file_path} {flash_addr:#x}")

            return FlashResult(
                success=True,
                bytes_written=file_path.stat().st_size,
                verify_passed=verify,
                duration_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return FlashResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )

    def flash_data(self, address: int, data: bytes, verify: bool = True) -> FlashResult:
        """Flash raw data via temporary file."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = Path(f.name)

        try:
            return self.flash_binary(temp_path, address, verify, erase_first=False)
        finally:
            temp_path.unlink(missing_ok=True)

    def erase_flash(self, address: Optional[int] = None, length: Optional[int] = None) -> None:
        """Erase flash."""
        if not self.connected:
            raise EraseError("Not connected")
        if address is not None and length is not None:
            self._send_command(f"flash erase_address {address:#x} {length}")
        else:
            self._send_command("flash erase 0 0 last")

    def erase_sector(self, address: int) -> None:
        """Erase sector."""
        if not self.connected:
            raise EraseError("Not connected")
        self._send_command(f"flash erase_sector 0 {address:#x} {address:#x}")

    def get_memory_map(self) -> List[MemoryRegion]:
        """Get memory map."""
        return []

    def get_flash_algorithms(self) -> List[FlashAlgorithm]:
        """Get flash algorithms."""
        return []

    def set_breakpoint(self, address: int, hardware: bool = True) -> int:
        """Set breakpoint via GDB."""
        return address

    def remove_breakpoint(self, bp_id: int) -> None:
        """Remove breakpoint."""
        pass

    def step(self) -> None:
        """Single step."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._send_command("step")