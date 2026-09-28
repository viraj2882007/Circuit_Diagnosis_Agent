"""
Probe factory for automatic probe selection and instantiation.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from .base import ProbeInterface, ProbeInterfaceType, ProbeCapabilities, ProbeError
from .pyocd_backend import PyOCDBackend
from .openocd_backend import OpenOCDBackend
from ..config import load_mcu_config

logger = logging.getLogger(__name__)


class ProbeFactory:
    """Factory for creating and managing debug probe instances."""

    # Probe backend priority per MCU family
    BACKEND_PRIORITY = {
        "stm32": ["pyocd", "openocd"],
        "esp32": ["openocd", "pyocd"],
        "esp32s2": ["openocd", "pyocd"],
        "esp32s3": ["openocd", "pyocd"],
        "esp32c3": ["openocd", "pyocd"],
        "esp32h2": ["openocd", "pyocd"],
        "rp2040": ["pyocd", "openocd"],
        "samd21": ["pyocd", "openocd"],
        "samd51": ["pyocd", "openocd"],
        "avr": ["openocd"],
    }

    # Probe interface support per backend
    BACKEND_INTERFACES = {
        "pyocd": [ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG],
        "openocd": [ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG, ProbeInterfaceType.UART],
    }

    def __init__(self, config_path: Optional[Path] = None):
        self.config = load_mcu_config(config_path)
        self._probe_cache: Dict[str, ProbeInterface] = {}

    def create_probe(self, mcu_family: str, probe_id: Optional[str] = None,
                     interface: Optional[ProbeInterfaceType] = None,
                     freq_khz: int = 1000, prefer_backend: Optional[str] = None) -> ProbeInterface:
        """Create probe instance for MCU family."""
        cache_key = f"{mcu_family}:{probe_id}:{interface}:{freq_khz}"
        if cache_key in self._probe_cache:
            return self._probe_cache[cache_key]

        family_config = self.config.get("families", {}).get(mcu_family, {})
        supported_probes = family_config.get("supported_probes", [])
        default_probe = family_config.get("default_probe", "cmsis-dap")

        # Determine probe ID
        if probe_id is None:
            probe_id = default_probe

        # Determine interface
        if interface is None:
            interfaces = family_config.get("probe_interfaces", ["swd"])
            interface = ProbeInterfaceType(interfaces[0])

        # Determine backend priority
        backends = self.BACKEND_PRIORITY.get(mcu_family, ["pyocd", "openocd"])
        if prefer_backend:
            backends = [prefer_backend] + [b for b in backends if b != prefer_backend]

        # Try each backend
        last_error = None
        for backend_name in backends:
            try:
                probe = self._create_backend(backend_name, mcu_family, probe_id, interface, freq_khz)
                self._probe_cache[cache_key] = probe
                return probe
            except Exception as e:
                last_error = e
                logger.debug(f"Backend {backend_name} failed for {mcu_family}: {e}")
                continue

        raise ProbeError(f"All backends failed for {mcu_family}: {last_error}")

    def _create_backend(self, backend_name: str, mcu_family: str,
                        probe_id: str, interface: ProbeInterfaceType,
                        freq_khz: int) -> ProbeInterface:
        """Create specific backend instance."""
        if backend_name == "pyocd":
            return PyOCDBackend(probe_id=probe_id, interface=interface, freq_khz=freq_khz)
        elif backend_name == "openocd":
            return OpenOCDBackend(
                probe_id=probe_id,
                interface=interface,
                target_family=mcu_family,
                freq_khz=freq_khz
            )
        else:
            raise ProbeError(f"Unknown backend: {backend_name}")

    def detect_probes(self) -> List[Dict[str, Any]]:
        """Detect connected debug probes."""
        probes = []

        # Try PyOCD probe detection
        try:
            from pyocd.probe.pydapaccess import CMSISDAPAccess
            from pyocd.probe.stlink_probe import STLinkProbe
            from pyocd.probe.jlink_probe import JLinkProbe
            from pyocd.probe.blackmagic_probe import BlackMagicProbe

            for probe_class in [CMSISDAPAccess, STLinkProbe, JLinkProbe, BlackMagicProbe]:
                try:
                    connected = probe_class.get_all_connected_probes()
                    for p in connected:
                        probes.append({
                            "type": probe_class.__name__,
                            "vid": p.vid,
                            "pid": p.pid,
                            "serial": p.serial_number,
                            "product": p.product_name,
                            "backend": "pyocd"
                        })
                except Exception:
                    pass
        except ImportError:
            pass

        return probes

    def auto_select_probe(self, mcu_family: str) -> Optional[str]:
        """Auto-select best available probe for MCU family."""
        detected = self.detect_probes()
        family_config = self.config.get("families", {}).get(mcu_family, {})
        supported = family_config.get("supported_probes", [])

        for probe in detected:
            probe_type = probe["type"].lower().replace("probe", "").replace("access", "")
            for supported_probe in supported:
                if supported_probe.lower() in probe_type or probe_type in supported_probe.lower():
                    return supported_probe

        return None

    def get_probe_capabilities(self, probe_id: str) -> Optional[ProbeCapabilities]:
        """Get capabilities for a probe type."""
        capabilities_map = {
            "stlink": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG],
                max_swd_freq_khz=4000,
                max_jtag_freq_khz=10000,
                supports_swo=True,
                supports_rtt=True,
            ),
            "jlink": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG],
                max_swd_freq_khz=8000,
                max_jtag_freq_khz=15000,
                supports_swo=True,
                supports_rtt=True,
            ),
            "cmsis-dap": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG],
                max_swd_freq_khz=2000,
                max_jtag_freq_khz=5000,
            ),
            "esp-prog": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.JTAG, ProbeInterfaceType.UART],
                max_jtag_freq_khz=10000,
            ),
            "blackmagic": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.SWD, ProbeInterfaceType.JTAG],
                max_swd_freq_khz=4000,
                max_jtag_freq_khz=10000,
                supports_swo=True,
                supports_rtt=True,
            ),
            "picoprobe": ProbeCapabilities(
                interfaces=[ProbeInterfaceType.SWD],
                max_swd_freq_khz=1000,
            ),
        }
        return capabilities_map.get(probe_id.lower())

    def clear_cache(self) -> None:
        """Clear probe instance cache."""
        for probe in self._probe_cache.values():
            if probe.connected:
                probe.disconnect()
        self._probe_cache.clear()


# Global factory instance
_factory: Optional[ProbeFactory] = None


def get_factory(config_path: Optional[Path] = None) -> ProbeFactory:
    """Get global probe factory instance."""
    global _factory
    if _factory is None:
        _factory = ProbeFactory(config_path)
    return _factory


def get_probe(mcu_family: str, probe_id: Optional[str] = None,
              interface: Optional[ProbeInterfaceType] = None,
              freq_khz: int = 1000) -> ProbeInterface:
    """Convenience function to get a probe instance."""
    return get_factory().create_probe(mcu_family, probe_id, interface, freq_khz)