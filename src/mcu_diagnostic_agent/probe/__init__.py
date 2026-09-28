"""
Probe abstraction layer for MCU Diagnostic Agent.
"""

from .base import (
    ProbeInterface, ProbeInterfaceType, ProbeCapabilities,
    ProbeError, ConnectionError, FlashError, EraseError, ResetError,
    TargetInfo, FlashResult, MemoryRegion, FlashAlgorithm
)
from .factory import ProbeFactory, get_factory, get_probe
from .target import (
    TargetMCU, MCUArchitecture, MemoryRegion as TargetMemoryRegion,
    PeripheralInfo, FlashAlgorithm as TargetFlashAlgorithm,
    get_target, get_targets_by_family, find_target_by_alias
)
from .pyocd_backend import PyOCDBackend
from .openocd_backend import OpenOCDBackend

__all__ = [
    # Base
    "ProbeInterface", "ProbeInterfaceType", "ProbeCapabilities",
    "ProbeError", "ConnectionError", "FlashError", "EraseError", "ResetError",
    "TargetInfo", "FlashResult", "MemoryRegion", "FlashAlgorithm",
    # Factory
    "ProbeFactory", "get_factory", "get_probe",
    # Target
    "TargetMCU", "MCUArchitecture", "TargetMemoryRegion",
    "PeripheralInfo", "TargetFlashAlgorithm",
    "get_target", "get_targets_by_family", "find_target_by_alias",
    # Backends
    "PyOCDBackend", "OpenOCDBackend",
]