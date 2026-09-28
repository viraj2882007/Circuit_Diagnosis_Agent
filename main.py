#!/usr/bin/env python3
"""
MCU Diagnostic Agent - Main Entry Point (Legacy)

Usage:
    python -m mcu_diagnostic_agent stm32 --part STM32F407VG --probe stlink
    python -m mcu_diagnostic_agent esp32 --suites basic,gpio,analog
    python -m mcu_diagnostic_agent rp2040 --freq 2000
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcu_diagnostic_agent.orchestrator.agent import main

if __name__ == "__main__":
    sys.exit(main())