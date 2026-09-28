"""
PyOCD backend implementation for probe interface.
"""

import logging
import time
from pathlib import Path
from typing import Optional, List

from .base import (
    ProbeInterface, ProbeInterfaceType, ProbeCapabilities,
    ProbeError, ConnectionError, FlashError, EraseError, ResetError,
    TargetInfo, FlashResult, MemoryRegion, FlashAlgorithm
)

logger = logging.getLogger(__name__)


class PyOCDBackend(ProbeInterface):
    """PyOCD-based debug probe backend."""

    def __init__(self, probe_id: Optional[str] = None,
                 interface: ProbeInterfaceType = ProbeInterfaceType.SWD,
                 target_override: Optional[str] = None,
                 freq_khz: int = 1000):
        super().__init__(probe_id, interface)
        self.target_override = target_override
        self.freq_khz = freq_khz
        self._session = None
        self._board = None
        self._target = None
        self._flash = None
        self._memory_map = None
        self._algorithms = None

    def _get_session_class(self):
        """Lazy import pyOCD to avoid hard dependency."""
        try:
            from pyocd.core.session import Session
            return Session
        except ImportError as e:
            raise ProbeError(f"PyOCD not installed: {e}. Install with: pip install pyocd")

    def connect(self, target_override: Optional[str] = None, freq_khz: int = 1000) -> TargetInfo:
        """Connect to target using PyOCD."""
        if self.connected:
            return self.target_info

        Session = self._get_session_class()

        try:
            # Create session with probe selection
            connect_kwargs = {}
            if self.probe_id:
                connect_kwargs['probe_id'] = self.probe_id
            if target_override or self.target_override:
                connect_kwargs['target_override'] = target_override or self.target_override

            self._session = Session(**connect_kwargs)
            self._board = self._session.board
            self._target = self._board.target
            self._flash = self._target.flash

            # Set frequency
            if freq_khz:
                self._target.set_frequency(freq_khz * 1000)
            elif self.freq_khz:
                self._target.set_frequency(self.freq_khz * 1000)

            # Get target info
            self.target_info = self._get_target_info()
            self._memory_map = self._get_memory_map()
            self._algorithms = self._get_flash_algorithms()
            self.connected = True

            logger.info(f"Connected to {self.target_info.part_number} via PyOCD")
            return self.target_info

        except Exception as e:
            raise ConnectionError(f"Failed to connect via PyOCD: {e}")

    def _get_target_info(self) -> TargetInfo:
        """Extract target information from PyOCD session."""
        target = self._target
        return TargetInfo(
            family=target.get_core_type().name if hasattr(target, 'get_core_type') else "Unknown",
            part_number=getattr(target, 'part_number', 'Unknown'),
            revision=getattr(target, 'revision', 'Unknown'),
            flash_size_kb=target.flash_size // 1024 if hasattr(target, 'flash_size') else 0,
            ram_size_kb=target.ram_size // 1024 if hasattr(target, 'ram_size') else 0,
            cpu_type=target.core_type.name if hasattr(target, 'core_type') else "Cortex-M",
            unique_id=target.get_unique_id() if hasattr(target, 'get_unique_id') else b"",
        )

    def _get_memory_map(self) -> List[MemoryRegion]:
        """Get memory map from target."""
        regions = []
        for region in self._target.memory_map:
            regions.append(MemoryRegion(
                start=region.start,
                length=region.length,
                name=region.name,
                is_flash=region.is_flash,
                is_ram=region.is_ram,
                permissions=region.permissions
            ))
        return regions

    def _get_flash_algorithms(self) -> List[FlashAlgorithm]:
        """Get flash algorithms from target."""
        algos = []
        if self._flash:
            for algo in self._flash.algorithms:
                algos.append(FlashAlgorithm(
                    name=algo.name,
                    family=algo.name.split('_')[0] if '_' in algo.name else algo.name,
                    start_address=algo.address_start,
                    page_size=algo.page_size,
                    sector_size=algo.sector_size,
                    flash_size=self._flash.flash_size,
                    ram_start=self._target.ram_start,
                    ram_size=self._target.ram_size,
                ))
        return algos

    def disconnect(self) -> None:
        """Disconnect from target."""
        if self._session:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing PyOCD session: {e}")
            finally:
                self._session = None
                self._board = None
                self._target = None
                self._flash = None
                self.connected = False

    def reset(self, halt: bool = True, run: bool = False) -> None:
        """Reset target."""
        if not self.connected:
            raise ResetError("Not connected")
        try:
            if halt:
                self._target.reset(halt=True)
            else:
                self._target.reset(halt=False)
                if run:
                    self._target.resume()
        except Exception as e:
            raise ResetError(f"Reset failed: {e}")

    def halt(self) -> None:
        """Halt target."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.halt()

    def resume(self) -> None:
        """Resume target."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.resume()

    def read_memory(self, address: int, length: int) -> bytes:
        """Read memory."""
        if not self.connected:
            raise ProbeError("Not connected")
        return self._target.read_memory_block8(address, length)

    def write_memory(self, address: int, data: bytes) -> None:
        """Write memory."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.write_memory_block8(address, data)

    def read_core_register(self, reg_name: str) -> int:
        """Read core register."""
        if not self.connected:
            raise ProbeError("Not connected")
        return self._target.read_core_register(reg_name)

    def write_core_register(self, reg_name: str, value: int) -> None:
        """Write core register."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.write_core_register(reg_name, value)

    def flash_binary(self, file_path: Path, address: Optional[int] = None,
                     verify: bool = True, erase_first: bool = True) -> FlashResult:
        """Flash binary file."""
        if not self.connected:
            raise FlashError("Not connected")

        start_time = time.time()
        try:
            if erase_first:
                self._flash.erase_all()

            with open(file_path, 'rb') as f:
                data = f.read()

            flash_addr = address or self._flash.address_start
            self._flash.program(flash_addr, data)

            bytes_written = len(data)
            verify_passed = False

            if verify:
                verify_passed = self._verify_flash(flash_addr, data)

            return FlashResult(
                success=True,
                bytes_written=bytes_written,
                verify_passed=verify_passed,
                duration_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return FlashResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )

    def flash_data(self, address: int, data: bytes, verify: bool = True) -> FlashResult:
        """Flash raw data."""
        if not self.connected:
            raise FlashError("Not connected")

        start_time = time.time()
        try:
            self._flash.program(address, data)
            bytes_written = len(data)
            verify_passed = False

            if verify:
                verify_passed = self._verify_flash(address, data)

            return FlashResult(
                success=True,
                bytes_written=bytes_written,
                verify_passed=verify_passed,
                duration_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return FlashResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )

    def _verify_flash(self, address: int, data: bytes) -> bool:
        """Verify flashed data."""
        try:
            read_back = self.read_memory(address, len(data))
            return read_back == data
        except Exception:
            return False

    def erase_flash(self, address: Optional[int] = None, length: Optional[int] = None) -> None:
        """Erase flash."""
        if not self.connected:
            raise EraseError("Not connected")
        if address is None and length is None:
            self._flash.erase_all()
        else:
            self._flash.erase(address, length)

    def erase_sector(self, address: int) -> None:
        """Erase single sector."""
        if not self.connected:
            raise EraseError("Not connected")
        self._flash.erase_sector(address)

    def get_memory_map(self) -> List[MemoryRegion]:
        """Get memory map."""
        return self._memory_map or []

    def get_flash_algorithms(self) -> List[FlashAlgorithm]:
        """Get flash algorithms."""
        return self._algorithms or []

    def set_breakpoint(self, address: int, hardware: bool = True) -> int:
        """Set breakpoint."""
        if not self.connected:
            raise ProbeError("Not connected")
        bp = self._target.set_breakpoint(address, hardware=hardware)
        return bp.id if hasattr(bp, 'id') else address

    def remove_breakpoint(self, bp_id: int) -> None:
        """Remove breakpoint."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.remove_breakpoint(bp_id)

    def step(self) -> None:
        """Single step."""
        if not self.connected:
            raise ProbeError("Not connected")
        self._target.step()