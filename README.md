# MCU Diagnostic Agent

An extensible MCU diagnostic agent with board-aware discovery, capability-based test planning, structured reports, and optional NVIDIA Nemotron analysis. Actual coverage depends on the selected board profile, diagnostic firmware/adapters, wiring, and available measurement equipment; the tool must not mark untested peripherals as passing.

## Supported Platforms

| Family | MCUs | Debug Interfaces | Probes |
| --- | --- | --- | --- |
| **STM32** | F0/F1/F3/F4/F7/G0/G4/H7/L0/L1/L4/L5/U5/WB/WL | SWD, JTAG | ST-Link, J-Link, CMSIS-DAP, Black Magic |
| **ESP32** | ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-H2 | JTAG, UART | ESP-Prog, J-Link, FTDI |
| **RP2040** | Raspberry Pi RP2040 | SWD | CMSIS-DAP, J-Link, PicoProbe |
| **Arduino** | AVR (Uno, Mega), SAMD (Zero, MKR) | UART, SWD, JTAG | UART bootloader, CMSIS-DAP |

## Features

- **Board-aware discovery and planning**: matches known USB serial identities to board profiles and previews board-specific checks
- **Peripheral diagnostics**: GPIO, ADC, UART, SPI, I2C, timers/PWM, memory and external-module checks when the correct board adapter and test conditions are available
- **Multi-probe support**: Works with ST-Link, J-Link, CMSIS-DAP, ESP-Prog, Black Magic Probe
- **Zephyr-based test firmware**: Portable, professional RTOS-based diagnostics
- **Comprehensive reporting**: HTML, JSON, and text reports with pass/fail analysis
- **Flash safety**: refuses to overwrite MCU firmware unless explicitly allowed; automatic restore/erase is not implemented
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

# Read-only serial-board discovery (does not reset or flash devices)
python -m mcu_diagnostic_agent.board_detection

# Preview a board-specific plan for an exact matched serial board
python -m mcu_diagnostic_agent.board_detection --plan COM9

# Print the plan as JSON for automation/integration
python -m mcu_diagnostic_agent.board_detection --plan COM9 --json
```

### Board-aware discovery and safety limits

The initial USB serial profile registry includes Arduino Uno R3, Mega 2560 R3, Leonardo, and Micro identities. Discovery uses exact configured USB VID/PID matches for automatic profile selection. A product/description hint is shown only as a low-confidence candidate; it does not silently choose a test plan. Boards using generic CH340/CP210x bridges, SWD-only targets, bootloader/DFU modes, or unregistered identities may require an explicit selection or another discovery adapter.

The discovery command is **read-only**. Its plan preview does not run tests, change pins, reset a board, or flash firmware. A planned test marked as requiring wiring, a firmware adapter, a device profile, or a measurement instrument is not yet an executed test. Actual PASS/FAIL results must come from recorded measurements. Peripheral absence (for example, no I2C ACK when no module is attached) is not by itself proof of a fault. SPI/UART devices and arbitrary external sensors cannot all be identified through one universal scan.

Memory write/flash tests are excluded from the default plan because they can change stored data or overwrite firmware. The project does not yet implement automatic backup and restoration of arbitrary application firmware.

### Run the Arduino Uno R3 diagnostic adapter

The board-specific sketch is maintained at `firmware/arduino_uno_r3/Uno_R3_Diagnostic.ino`. Upload it manually using Arduino IDE with **Arduino Uno** selected. The host runner will not upload firmware and will refuse to run Uno-specific commands unless the serial firmware reports board ID `ARDUINO_UNO_R3` and version `2`.

Close Arduino IDE's Serial Monitor before running the host adapter. Opening COM ports commonly auto-resets an Uno; the runner asks for confirmation unless `--yes-reset` is supplied.

```powershell
# Passive board identification and test-plan preview
mcu-board

# Verify board identity and the manually uploaded diagnostic firmware
mcu-uno-test --port COM9

# Run GPIO, PWM, ADC, onboard LED and SPI loopback checks.
# This mode prompts for each jumper/wiring change and records skipped checks as skipped.
mcu-uno-test --port COM9 --interactive

# Optional I2C scan + known chip-ID checks + AI analysis; check voltage/pull-ups first.
mcu-uno-test --port COM9 --identify-i2c --ai-analysis
```

The interactive checks require the user to move one jumper at a time. D0/D1 are reserved for USB serial. The I2C scanner reports addresses that ACK. With the explicit --identify-i2c option, the adapter additionally reads documented identity registers for a small known-profile registry (BMP280, BME280, MPU-6050, LIS3DH and LSM6DS3). A matching chip ID identifies a device model but does not prove its full function; unidentified addresses remain unknown observations, never automatic failures. The adapter asks for confirmation before probing the bus and only reads profile-listed identity registers.

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

## Nemotron 3 Ultra AI diagnosis and external peripherals

Optional AI analysis uses NVIDIA's OpenAI-compatible NIM endpoint. Create an API key in the
NVIDIA API catalog and set it in your shell; never commit the key.

PowerShell:
```powershell
$env:NVIDIA_API_KEY = "YOUR_NVIDIA_API_KEY"
```

Run a diagnostic with evidence-based AI interpretation:
```bash
python -m mcu_diagnostic_agent stm32 --part STM32F407VG --probe stlink \
  --allow-firmware-overwrite --ai-analysis --external-observations examples/external-observations.example.json
```

The firmware overwrite flag is deliberately explicit. The current implementation does not
back up and restore original MCU firmware; after consent to flashing, the diagnostic firmware
may remain on the device. Make sure you have a known-good recovery path before using this
hardware workflow. Cleanup never automatically erases target flash.

### External observation file

The external observation JSON lets a user or a hardware-specific adapter record test evidence
for connected sensors, displays, EEPROMs, USB devices, and other peripherals. Example:

```json
{
  "board": "Example dev board",
  "peripherals": [
    {
      "name": "I2C OLED",
      "interface": "I2C",
      "status": "fail",
      "expected": "ACK at 0x3C",
      "observed": "No ACK observed at 0x3C",
      "evidence": ["I2C scan repeated three times with the device powered"],
      "measurements": {"vcc_v": 3.28},
      "notes": "Address and supply are from the device datasheet"
    }
  ]
}
```

Allowed status values are `pass`, `fail`, `warning`, `unknown`, and `not_tested`.
This JSON is evidence input, not a claim that the host automatically tested a device. Reliable
automatic external diagnosis requires a supported board/test adapter, correctly wired hardware,
and device-specific checks. The AI report distinguishes evidence from hypotheses and discusses
likely causes, how the fault may have occurred, prevention, repairability, and replacement or
technician escalation when repair is unsafe or unsupported.

The optional `--nemotron-model` argument defaults to
`nvidia/nemotron-3-ultra-550b-a55b`. AI analysis requires `NVIDIA_API_KEY`; diagnostic and
external-observation reporting still completes if the AI service is unavailable.
