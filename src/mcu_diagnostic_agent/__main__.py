"""
MCU Diagnostic Agent - Module Entry Point

Usage:
    python -m mcu_diagnostic_agent stm32 --part STM32F407VG --probe stlink
    python -m mcu_diagnostic_agent esp32 --suites basic,gpio,analog
    python -m mcu_diagnostic_agent rp2040 --freq 2000
"""

import sys
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcu_diagnostic_agent.orchestrator.agent import main

if __name__ == "__main__":
    sys.exit(main())