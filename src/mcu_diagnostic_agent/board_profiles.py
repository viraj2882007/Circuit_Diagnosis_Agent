"""Board-specific capabilities and safety-aware diagnostic plans.

Profiles are deliberately conservative: an exact USB VID/PID can identify a known
board interface, while an ambiguous USB bridge is only a hint. A profile is not proof
that every component on a board is healthy.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BoardProfile:
    """Static capabilities for one known development-board revision."""

    board_id: str
    display_name: str
    mcu_family: str
    mcu_part: str
    usb_vid_pids: Tuple[Tuple[int, int], ...]
    description_hints: Tuple[str, ...]
    digital_pins: Tuple[str, ...]
    analog_inputs: Tuple[str, ...]
    pwm_pins: Tuple[str, ...]
    uart_pins: Tuple[Tuple[str, str], ...]
    i2c_pins: Tuple[Tuple[str, str], ...]
    spi_pins: Tuple[Tuple[str, str], ...]
    external_interrupt_pins: Tuple[str, ...]
    adc_resolution_bits: int
    dac_outputs: Tuple[str, ...]
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        result = asdict(self)
        result["usb_vid_pids"] = [
            {"vid": vid, "pid": pid, "hex": "{:04X}:{:04X}".format(vid, pid)}
            for vid, pid in self.usb_vid_pids
        ]
        return result


def _pins(prefix: str, start: int, end: int) -> Tuple[str, ...]:
    return tuple("{}{}".format(prefix, pin) for pin in range(start, end + 1))


BOARD_PROFILES: Dict[str, BoardProfile] = {
    "arduino_uno_r3": BoardProfile(
        board_id="arduino_uno_r3",
        display_name="Arduino Uno R3",
        mcu_family="arduino",
        mcu_part="ATmega328P",
        # Official Uno R3 USB interface IDs. Clones with CH340/CP210x bridges
        # are not auto-confirmed because those bridge IDs are shared by many boards.
        usb_vid_pids=((0x2341, 0x0043), (0x2A03, 0x0043)),
        description_hints=("arduino uno", "uno r3"),
        digital_pins=_pins("D", 0, 13),
        analog_inputs=_pins("A", 0, 5),
        pwm_pins=("D3", "D5", "D6", "D9", "D10", "D11"),
        uart_pins=(("TX", "D1"), ("RX", "D0")),
        i2c_pins=(("SDA", "A4"), ("SCL", "A5")),
        spi_pins=(("SS", "D10"), ("MOSI", "D11"), ("MISO", "D12"), ("SCK", "D13")),
        external_interrupt_pins=("D2", "D3"),
        adc_resolution_bits=10,
        dac_outputs=(),
        notes=(
            "USB identity identifies the board interface, not the electrical health of the MCU.",
            "D0/D1 are shared with the hardware UART and should be kept free during USB serial tests.",
            "A4/A5 are shared with the I2C bus; D10-D13 are shared with SPI.",
            "The classic Uno R3 has no native DAC output.",
        ),
    ),
    "arduino_mega_2560_r3": BoardProfile(
        board_id="arduino_mega_2560_r3",
        display_name="Arduino Mega 2560 R3",
        mcu_family="arduino",
        mcu_part="ATmega2560",
        usb_vid_pids=((0x2341, 0x0042), (0x2A03, 0x0042)),
        description_hints=("arduino mega 2560", "mega 2560"),
        digital_pins=_pins("D", 0, 53),
        analog_inputs=_pins("A", 0, 15),
        pwm_pins=("D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "D44", "D45", "D46"),
        uart_pins=(("TX0", "D1"), ("RX0", "D0"), ("TX1", "D18"), ("RX1", "D19"),
                   ("TX2", "D16"), ("RX2", "D17"), ("TX3", "D14"), ("RX3", "D15")),
        i2c_pins=(("SDA", "D20"), ("SCL", "D21")),
        spi_pins=(("SS", "D53"), ("MOSI", "D51"), ("MISO", "D50"), ("SCK", "D52")),
        external_interrupt_pins=("D2", "D3", "D18", "D19", "D20", "D21"),
        adc_resolution_bits=10,
        dac_outputs=(),
        notes=(
            "USB identity identifies the board interface, not the electrical health of the MCU.",
            "D0/D1 are shared with Serial0; use a different UART when testing other serial peripherals.",
            "The classic Mega 2560 R3 has no native DAC output.",
        ),
    ),
    "arduino_leonardo": BoardProfile(
        board_id="arduino_leonardo",
        display_name="Arduino Leonardo",
        mcu_family="arduino",
        mcu_part="ATmega32U4",
        usb_vid_pids=((0x2341, 0x8036), (0x2A03, 0x8036)),
        description_hints=("arduino leonardo", "leonardo"),
        digital_pins=_pins("D", 0, 13),
        analog_inputs=_pins("A", 0, 11),
        pwm_pins=("D3", "D5", "D6", "D9", "D10", "D11", "D13"),
        uart_pins=(("TX", "D1"), ("RX", "D0")),
        i2c_pins=(("SDA", "D2"), ("SCL", "D3")),
        spi_pins=(("MOSI", "ICSP-MOSI"), ("MISO", "ICSP-MISO"), ("SCK", "ICSP-SCK")),
        external_interrupt_pins=("D0", "D1", "D2", "D3", "D7"),
        adc_resolution_bits=10,
        dac_outputs=(),
        notes=(
            "The ATmega32U4 provides native USB; its USB interface differs from Uno R3.",
            "SPI is exposed on the ICSP header on the standard Leonardo layout.",
            "Check the exact board revision and pinout before attaching loopback jumpers.",
        ),
    ),
    "arduino_micro": BoardProfile(
        board_id="arduino_micro",
        display_name="Arduino Micro",
        mcu_family="arduino",
        mcu_part="ATmega32U4",
        usb_vid_pids=((0x2341, 0x8037), (0x2A03, 0x8037)),
        description_hints=("arduino micro",),
        digital_pins=_pins("D", 0, 13),
        analog_inputs=_pins("A", 0, 11),
        pwm_pins=("D3", "D5", "D6", "D9", "D10", "D11", "D13"),
        uart_pins=(("TX", "D1"), ("RX", "D0")),
        i2c_pins=(("SDA", "D2"), ("SCL", "D3")),
        spi_pins=(("MOSI", "ICSP-MOSI"), ("MISO", "ICSP-MISO"), ("SCK", "ICSP-SCK")),
        external_interrupt_pins=("D0", "D1", "D2", "D3", "D7"),
        adc_resolution_bits=10,
        dac_outputs=(),
        notes=(
            "The ATmega32U4 provides native USB; its USB interface differs from Uno R3.",
            "SPI is exposed on the ICSP header on the standard Micro layout.",
            "Check the exact board revision and pinout before attaching loopback jumpers.",
        ),
    ),
}


def get_board_profile(board_id: str) -> Optional[BoardProfile]:
    """Return a known board profile by its stable ID."""
    return BOARD_PROFILES.get(board_id.strip().lower())


def find_profiles_by_usb_id(vid: Optional[int], pid: Optional[int]) -> List[BoardProfile]:
    """Return exact VID/PID matches. Unknown or absent identifiers return no match."""
    if vid is None or pid is None:
        return []
    return [
        profile
        for profile in BOARD_PROFILES.values()
        if (vid, pid) in profile.usb_vid_pids
    ]


def build_diagnostic_plan(profile: BoardProfile, include_destructive: bool = False) -> Dict[str, Any]:
    """Build a plan for a board without executing tests or touching hardware.

    status is an availability statement, not a test result. Actual results must
    be produced by a board adapter and recorded only after a measurement is taken.
    """
    tests: List[Dict[str, Any]] = [
        {
            "id": "usb_serial_enumeration",
            "category": "host_interface",
            "description": "Confirm the board's USB serial interface is visible to the host.",
            "status": "available",
            "risk": "non_destructive",
            "automatic": True,
            "prerequisites": [],
        },
        {
            "id": "mcu_signature_read",
            "category": "chip_identification",
            "description": "Read the MCU signature through a supported bootloader/programmer tool.",
            "status": "requires_adapter",
            "risk": "read_only_but_may_reset_target",
            "automatic": False,
            "prerequisites": ["Compatible read-only adapter/tool", "Close other applications using the port"],
        },
        {
            "id": "gpio_loopback",
            "category": "gpio",
            "description": "Check digital input/output by connecting one output pin to one input pin at a time.",
            "status": "requires_wiring",
            "risk": "low_when_wired_as_documented",
            "automatic": False,
            "pins": list(profile.digital_pins),
            "excluded_pins": [pin for pin in ("D0", "D1") if pin in profile.digital_pins],
            "prerequisites": [
                "Compatible board-specific diagnostic sketch",
                "Jumper wires and a documented pair-by-pair test sequence",
                "Remove loopback jumpers before using pins for another interface",
            ],
        },
        {
            "id": "adc_input_sweep",
            "category": "adc",
            "description": "Check each analog input against known, safe reference levels.",
            "status": "requires_stimulus_and_adapter",
            "risk": "low_only_with_verified_voltage_and_wiring",
            "automatic": False,
            "pins": list(profile.analog_inputs),
            "resolution_bits": profile.adc_resolution_bits,
            "prerequisites": [
                "Board-specific ADC test firmware",
                "Known input stimulus within the board's allowed voltage range",
                "Never connect an unknown voltage directly to an analog input",
            ],
        },
        {
            "id": "pwm_output_check",
            "category": "timers_pwm",
            "description": "Check PWM output presence; accurate frequency/duty-cycle validation requires capture hardware.",
            "status": "requires_wiring_and_adapter",
            "risk": "low_when_wired_as_documented",
            "automatic": False,
            "pins": list(profile.pwm_pins),
            "prerequisites": [
                "Board-specific PWM test firmware",
                "Loopback to a documented input or a logic analyzer/oscilloscope",
            ],
        },
        {
            "id": "i2c_bus_scan",
            "category": "i2c",
            "description": "Scan the known I2C bus for responding addresses; this does not identify every device.",
            "status": "requires_firmware_adapter",
            "risk": "low_on_a_known_bus_with_compatible_voltage_levels",
            "automatic": False,
            "pins": [dict(name=name, pin=pin) for name, pin in profile.i2c_pins],
            "prerequisites": [
                "Board-specific I2C scan firmware",
                "Verify bus voltage and pull-ups before connecting modules",
                "No ACK may mean no device is attached; it is not by itself proof of a board fault",
            ],
        },
        {
            "id": "spi_loopback",
            "category": "spi",
            "description": "Check SPI signal paths with a documented MOSI-to-MISO loopback.",
            "status": "requires_wiring_and_adapter",
            "risk": "low_when_wired_as_documented",
            "automatic": False,
            "pins": [dict(name=name, pin=pin) for name, pin in profile.spi_pins],
            "prerequisites": [
                "Board-specific SPI test firmware",
                "Verified pin mapping and MOSI-to-MISO jumper",
                "Disconnect external SPI devices unless the test profile says otherwise",
            ],
        },
        {
            "id": "external_peripheral_profile_test",
            "category": "external_peripherals",
            "description": "Run the matched driver's checks for an explicitly identified sensor/module.",
            "status": "requires_device_profile",
            "risk": "depends_on_device_profile",
            "automatic": False,
            "prerequisites": [
                "Identify the peripheral model or select a matching profile",
                "Verify connector, supply voltage, logic levels, wiring and bus address",
                "Use sensor-specific expectations or a calibrated measurement reference",
            ],
        },
        {
            "id": "external_i2c_discovery",
            "category": "external_peripherals",
            "description": "Look for I2C ACK responses on the configured bus; response alone does not prove device health.",
            "status": "requires_firmware_adapter",
            "risk": "low_on_a_known_bus_with_compatible_voltage_levels",
            "automatic": False,
            "prerequisites": [
                "Known I2C wiring and compatible logic levels",
                "Bus scanner adapter",
                "Device profile to map an address to a product",
            ],
        },
        {
            "id": "external_spi_uart_discovery",
            "category": "external_peripherals",
            "description": "SPI and UART peripherals need device-specific protocols; there is no universal scan that identifies all modules.",
            "status": "requires_device_profile",
            "risk": "depends_on_device_profile",
            "automatic": False,
            "prerequisites": [
                "Select a compatible device profile or protocol adapter",
                "Do not transmit arbitrary commands to unknown devices",
            ],
        },
    ]

    if include_destructive:
        tests.extend([
            {
                "id": "eeprom_write_read",
                "category": "memory",
                "description": "Write/read a dedicated test region only after the user approves the data-loss risk.",
                "status": "explicit_approval_required",
                "risk": "destructive_to_test_region",
                "automatic": False,
                "prerequisites": [
                    "Explicit user confirmation",
                    "Reserved test addresses or a documented backup/restore strategy",
                ],
            },
            {
                "id": "flash_integrity",
                "category": "memory",
                "description": "Flash tests can overwrite the installed application or bootloader.",
                "status": "blocked_without_recovery_strategy",
                "risk": "destructive",
                "automatic": False,
                "prerequisites": [
                    "Validated recovery/backup strategy",
                    "Explicit user confirmation",
                    "Board-specific flash layout and bootloader protection rules",
                ],
            },
        ])
    else:
        tests.append({
            "id": "memory_write_tests",
            "category": "memory",
            "description": "EEPROM/flash write tests are omitted from the default plan because they can change user data or firmware.",
            "status": "excluded_by_default",
            "risk": "destructive",
            "automatic": False,
            "prerequisites": ["Explicit opt-in and a validated board-specific recovery strategy"],
        })

    adapter_available = profile.board_id == "arduino_uno_r3"
    return {
        "board": {
            "board_id": profile.board_id,
            "display_name": profile.display_name,
            "mcu_family": profile.mcu_family,
            "mcu_part": profile.mcu_part,
        },
        "adapter": {
            "id": "arduino_uno_r3_serial_v2" if adapter_available else None,
            "implementation_available": adapter_available,
            "mode": "manual_firmware_upload_then_host_control" if adapter_available else "profile_and_plan_preview_only",
            "note": (
                "A dedicated Uno R3 sketch and serial host adapter are implemented; "
                "the sketch must be uploaded manually before hardware tests."
                if adapter_available
                else "This board has a capability profile, but a board-specific execution adapter "
                     "and matching diagnostic firmware are not implemented yet."
            ),
        },
        "plan_only": True,
        "execution_started": False,
        "warning": (
            "This is a capability-aware test plan, not a test result. Unsupported, "
            "unwired or unmeasured features must remain not tested."
        ),
        "tests": tests,
        "not_supported": {
            "dac_outputs": list(profile.dac_outputs) if profile.dac_outputs else [],
            "dac_note": (
                "This profile has no native DAC outputs."
                if not profile.dac_outputs
                else "DAC pins are listed for this profile."
            ),
        },
    }
