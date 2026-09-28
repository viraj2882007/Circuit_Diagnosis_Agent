"""
Probe Interface - Abstract base class for debug probe backends.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ProbeInterfaceType(Enum):
    """Debug interface types."""
    SWD = "swd"
    JTAG = "jtag"
    UART = "uart"


class ProbeError(Exception):
    """Base exception for probe errors."""
    pass


class ConnectionError(ProbeError):
    """Connection failed."""
    pass


class FlashError(ProbeError):
    """Flash operation failed."""
    pass


class EraseError(ProbeError):
    """Erase operation failed."""
    pass


class ResetError(ProbeError):
    """Reset operation failed."""
    pass


@dataclass
class TargetInfo:
    """Target MCU information."""
    family: str
    part_number: str
    revision: str
    flash_size_kb: int
    ram_size_kb: int
    cpu_type: str
    unique_id: bytes = b""


@dataclass
class MemoryRegion:
    """Memory region descriptor."""
    start: int
    length: int
    name: str
    is_flash: bool
    is_ram: bool
    permissions: str = "rw"


@dataclass
class FlashAlgorithm:
    """Flash algorithm descriptor."""
    name: str
    family: str
    start_address: int
    page_size: int
    sector_size: int
    flash_size: int
    ram_start: int
    ram_size: int


@dataclass
class FlashResult:
    """Flash operation result."""
    success: bool
    bytes_written: int = 0
    verify_passed: bool = False
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ProbeCapabilities:
    """Probe capabilities."""
    interfaces: List[ProbeInterfaceType] = field(default_factory=list)
    max_swd_freq_khz: int = 4000
    max_jtag_freq_khz: int = 10000
    supports_swo: bool = False
    supports_rtt: bool = False


class ProbeInterface(ABC):
    """Abstract debug probe interface."""

    def __init__(self, probe_id: Optional[str] = None,
                 interface: ProbeInterfaceType = ProbeInterfaceType.SWD):
        self.probe_id = probe_id
        self.interface = interface
        self.connected = False
        self.target_info: Optional[TargetInfo] = None

    @abstractmethod
    def connect(self, target_override: Optional[str] = None,
                freq_khz: int = 1000) -> TargetInfo:
        """Connect to target MCU."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from target."""
        pass

    @abstractmethod
    def reset(self, halt: bool = True, run: bool = False) -> None:
        """Reset target."""
        pass

    @abstractmethod
    def halt(self) -> None:
        """Halt target."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resume target."""
        pass

    @abstractmethod
    def read_memory(self, address: int, length: int) -> bytes:
        """Read memory from target."""
        pass

    @abstractmethod
    def write_memory(self, address: int, data: bytes) -> None:
        """Write memory to target."""
        pass

    @abstractmethod
    def read_core_register(self, reg_name: str) -> int:
        """Read core register."""
        pass

    @abstractmethod
    def write_core_register(self, reg_name: str, value: int) -> None:
        """Write core register."""
        pass

    @abstractmethod
    def flash_binary(self, file_path: Path, address: Optional[int] = None,
                     verify: bool = True, erase_first: bool = True) -> FlashResult:
        """Flash binary file to target."""
        pass

    @abstractmethod
    def flash_data(self, address: int, data: bytes, verify: bool = True) -> FlashResult:
        """Flash raw data to target."""
        pass

    @abstractmethod
    def erase_flash(self, address: Optional[int] = None, length: Optional[int] = None) -> None:
        """Erase flash memory."""
        pass

    @abstractmethod
    def erase_sector(self, address: int) -> None:
        """Erase single sector."""
        pass

    @abstractmethod
    def get_memory_map(self) -> List[MemoryRegion]:
        """Get memory map."""
        pass

    @abstractmethod
    def get_flash_algorithms(self) -> List[FlashAlgorithm]:
        """Get flash algorithms."""
        pass

    @abstractmethod
    def set_breakpoint(self, address: int, hardware: bool = True) -> int:
        """Set breakpoint."""
        pass

    @abstractmethod
    def remove_breakpoint(self, bp_id: int) -> None:
        """Remove breakpoint."""
        pass

    @abstractmethod
    def step(self) -> None:
        """Single step."""
        pass