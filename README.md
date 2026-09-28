# MCU Diagnostic Agent

A comprehensive diagnostic tool for MCU-based projects that automatically tests all peripherals and identifies faulty hardware.

## Supported Platforms

| Family | MCUs | Debug Interfaces | Probes |
| --- | --- | --- | --- |
| **STM32** | F0/F1/F3/F4/F7/G0/G4/H7/L0/L1/L4/L5/U5/WB/WL | SWD, JTAG | ST-Link, J-Link, CMSIS-DAP, Black Magic |
| **ESP32** | ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-H2 | JTAG, UART | ESP-Prog, J-Link, FTDI |
| **RP2040** | Raspberry Pi RP2040 | SWD | CMSIS-DAP, J-Link, PicoProbe |
| **Arduino** | AVR (Uno, Mega), SAMD (Zero, MKR) | UART, SWD, JTAG | UART bootloader, CMSIS-DAP |

## Features

- **Automated peripheral testing**: GPIO, ADC, DAC, UART, SPI, I2C, Timers, PWM, Flash, RAM
- **Multi-probe support**: Works with ST-Link, J-Link, CMSIS-DAP, ESP-Prog, Black Magic Probe
- **Zephyr-based test firmware**: Portable, professional RTOS-based diagnostics
- **Comprehensive reporting**: HTML, JSON, and text reports with pass/fail analysis
- **Non-destructive**: Restores original firmware after testing
- **Extensible**: Easy to add new test suites and MCU families

## Quick Start

### Prerequisites

1. **Python 3.9+** with dependencies:
```bash
pip install -r requirements.txt
```

2. **Zephyr RTOS** (for firmware building):
```bash
# Follow Zephyr getting started guide
west init zephyr
cd zephyr
west update
west zephyr-export
```

3. **Debug probe** connected to target MCU

### Installation

```bash
git clone <this-repo>
cd mcu_diagnostic_agent
pip install -e .
```

### Usage

```bash
# Basic STM32 test with ST-Link
python -m mcu_diagnostic_agent stm32 --part STM32F407VG --probe stlink

# ESP32 with specific test suites
python -m mcu_diagnostic_agent esp32 --suites basic,gpio,analog,communication

# RP2040 with higher debug frequency
python -m mcu_diagnostic_agent rp2040 --freq 4000

# Arduino Uno via UART bootloader
python -m mcu_diagnostic_agent arduino --part ATMEGA328P --interface uart --probe /dev/ttyUSB0

# Use pre-built firmware (skip Zephyr build)
python -m mcu_diagnostic_agent stm32 --firmware ./build/zephyr/zephyr.bin

# Verbose output
python -m mcu_diagnostic_agent stm32 -v
```

### Test Suites

| Suite | Tests | Description |
| --- | --- | --- |
| `basic` | cpu_id, ram_march_quick, flash_id, clock_check, gpio_toggle, entropy | Core functionality |
| `gpio` | gpio_output, gpio_input_pullup, gpio_input_pulldown, gpio_interrupt, gpio_short_detect | All GPIO modes |
| `analog` | adc_internal_temp, adc_vref, adc_external, dac_output, dac_adc_loopback | ADC/DAC |
| `communication` | uart_loopback, uart_baud_rates, spi_loopback, spi_frequency, i2c_scan, i2c_eeprom, i2c_speed | Serial interfaces |
| `timing` | pwm_output, timer_count, input_capture, rtc_test | Timers/PWM |
| `memory` | flash_write_read, flash_erase, ram_march, ram_extended_march | Memory integrity |
| `clock` | sys_clock, clock_control, external_crystal, pll_config | Clock subsystem |
| `advanced` | usb_enumerate, wifi_scan, bluetooth_adv, ethernet_link, crypto_accel | Advanced features |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Agent (Python)                      │
├─────────────────────────────────────────────────────────────┤
│  Orchestrator → Probe Factory → [PyOCD / OpenOCD Backend]  │
│       │                                                      │
│       ├── Firmware Builder (Zephyr/CMake)                   │
│       ├── Test Runner (Serial/RTT)                          │
│       └── Report Generator (HTML/JSON/Text)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                    SWD/JTAG/UART
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Target MCU (Zephyr Test Firmware)              │
├─────────────────────────────────────────────────────────────┤
│  Test Framework → [GPIO/ADC/DAC/UART/SPI/I2C/Timer Tests]  │
│       │                                                      │
│       └── Reporting (Binary protocol + JSON + Text)         │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
mcu_diagnostic_agent/
├── config/
│   └── mcu_families.yaml          # MCU/probe/test configuration
├── src/
│   ├── mcu_diagnostic_agent/
│   │   ├── __init__.py
│   │   ├── __main__.py            # Module entry point
│   │   ├── probe/                 # Probe abstraction layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Abstract interface
│   │   │   ├── pyocd_backend.py   # PyOCD implementation
│   │   │   ├── openocd_backend.py # OpenOCD implementation
│   │   │   ├── factory.py         # Probe selection/creation
│   │   │   └── target.py          # Target MCU definitions
│   │   ├── firmware/
│   │   │   ├── __init__.py
│   │   │   └── builder.py         # Zephyr firmware builder
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py           # Main diagnostic agent
│   │   │   └── test_runner.py     # Test execution/collection
│   │   └── reporting/
│   │       ├── __init__.py
│   │       └── generator.py       # Report generation
├── zephyr_app/                    # Zephyr test firmware
│   ├── src/
│   │   ├── main.c                 # Firmware entry point
│   │   ├── tests/                 # Peripheral test implementations
│   │   └── comm/                  # Serial reporting protocol
│   ├── boards/                    # Board-specific configs
│   ├── CMakeLists.txt
│   └── prj.conf
├── requirements.txt
├── pyproject.toml
├── setup.py
└── main.py                        # CLI entry point (legacy)
```

## Adding New Tests

1. Create test implementation in `zephyr_app/src/tests/<peripheral>_tests.c`
2. Add test cases to the suite array
3. Include in `zephyr_app/CMakeLists.txt`
4. Rebuild firmware

## Adding New MCU Support

1. Add family config to `config/mcu_families.yaml`
2. Add target definition to `src/mcu_diagnostic_agent/probe/target.py`
3. Add Zephyr board mapping in `src/mcu_diagnostic_agent/firmware/builder.py`
4. Create board config in `zephyr_app/boards/`

## License

MIT License - See LICENSE file for details.