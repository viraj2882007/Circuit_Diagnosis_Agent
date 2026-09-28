"""
Configuration loader for MCU diagnostic agent.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CONFIG_PATH: Optional[Path] = None


def load_mcu_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load MCU family and probe configuration."""
    global _CONFIG_CACHE, _CONFIG_PATH

    if _CONFIG_CACHE is not None and config_path is None:
        return _CONFIG_CACHE

    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "mcu_families.yaml"

    _CONFIG_PATH = config_path

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return _get_default_config()

    try:
        with open(config_path) as f:
            _CONFIG_CACHE = yaml.safe_load(f)
        logger.info(f"Loaded config from {config_path}")
        return _CONFIG_CACHE
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return _get_default_config()


def _get_default_config() -> Dict[str, Any]:
    """Return minimal default configuration."""
    return {
        "families": {
            "stm32": {
                "name": "STM32",
                "probe_interfaces": ["swd", "jtag"],
                "default_probe": "stlink",
                "supported_probes": ["stlink", "jlink", "cmsis-dap"],
            },
            "esp32": {
                "name": "ESP32",
                "probe_interfaces": ["jtag", "uart"],
                "default_probe": "esp-prog",
                "supported_probes": ["esp-prog", "jlink", "ftdi"],
            },
            "rp2040": {
                "name": "RP2040",
                "probe_interfaces": ["swd"],
                "default_probe": "cmsis-dap",
                "supported_probes": ["cmsis-dap", "jlink", "picoprobe"],
            },
            "arduino": {
                "name": "Arduino",
                "probe_interfaces": ["uart", "swd"],
                "default_probe": "uart",
                "supported_probes": ["uart", "cmsis-dap"],
            },
        },
        "probes": {},
        "test_suites": {},
    }


def get_family_config(family: str) -> Dict[str, Any]:
    """Get configuration for specific MCU family."""
    config = load_mcu_config()
    return config.get("families", {}).get(family.lower(), {})


def get_probe_config(probe_id: str) -> Dict[str, Any]:
    """Get configuration for specific probe."""
    config = load_mcu_config()
    return config.get("probes", {}).get(probe_id.lower(), {})


def get_test_suite(suite_name: str) -> Dict[str, Any]:
    """Get test suite configuration."""
    config = load_mcu_config()
    return config.get("test_suites", {}).get(suite_name, {})


def reload_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Force reload configuration."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    return load_mcu_config(config_path)