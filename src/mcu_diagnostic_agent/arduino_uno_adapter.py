"""Host runner for the board-specific Arduino Uno R3 diagnostic sketch.

This runner never uploads firmware. The matching sketch must be uploaded manually
from firmware/arduino_uno_r3/arduino_uno_r3.ino before running pin tests.
"""

import argparse
from dataclasses import asdict
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import serial

from .ai_diagnosis import generate_ai_analysis
from .avrdude_support import read_atmega328p_signature
from .board_detection import BoardDetection, detect_connected_boards
from .external_devices import match_i2c_identity, profiles_for_i2c_address
from .peripheral_observations import load_external_observations
from .reporting.generator import (
    DiagnosticReport,
    ReportGenerator,
    SuiteResultData,
    TestResultData,
)

_READY_MARKER = "UNO R3 DIAGNOSTIC SKETCH READY"
_INFO_MARKER = "INFO RESULT: PASS"


def parse_pair_results(lines: Sequence[str]) -> List[Tuple[str, str, str]]:
    """Parse direction-level results emitted by the Uno diagnostic sketch."""
    parsed: List[Tuple[str, str, str]] = []
    pattern = re.compile(
        r"^(D\d+ output -> D\d+ input):.*=> (PASS|FAIL)$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.search(line.strip())
        if match:
            parsed.append((match.group(1), match.group(2).lower(), line.strip()))
    return parsed


def parse_adc_measurement(line: str) -> Optional[int]:
    """Extract an ADC raw reading from a firmware result line."""
    match = re.search(r"average analogRead=(\d+)", line)
    return int(match.group(1)) if match else None


def parse_firmware_duration(line: str) -> Optional[float]:
    """Extract the duration measured by the target firmware, not a host-side estimate."""
    match = re.search(r"duration_ms=(\d+(?:\.\d+)?)", line, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_i2c_addresses(lines: Sequence[str]) -> List[int]:
    """Return I2C addresses reported by the scan command, without inferring device identity."""
    addresses: List[int] = []
    pattern = re.compile(r"^I2C_ADDR:0x([0-9A-F]{1,2})$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            address = int(match.group(1), 16)
            if address not in addresses:
                addresses.append(address)
    return addresses


def _test_result(
    name: str,
    suite: str,
    status: str,
    details: str,
    duration_ms: Optional[float] = None,
    measurements: Optional[List[float]] = None,
) -> TestResultData:
    return TestResultData(
        name=name,
        suite=suite,
        status=status,
        duration_ms=duration_ms,
        details=details,
        measurements=measurements or [],
        timestamp=time.time_ns() / 1_000_000_000,
    )


def _make_suite(name: str, tests: List[TestResultData]) -> SuiteResultData:
    measured = [test.duration_ms for test in tests]
    suite_duration = (
        sum(value for value in measured if value is not None)
        if tests and all(value is not None for value in measured)
        else None
    )
    return SuiteResultData(
        name=name,
        tests=tests,
        passed=sum(test.status == "pass" for test in tests),
        failed=sum(test.status in {"fail", "error"} for test in tests),
        skipped=sum(test.status in {"skip", "skipped"} for test in tests),
        duration_ms=suite_duration,
    )


def _derive_untested_features(
    suites: List[SuiteResultData],
    scan_i2c: bool,
    identify_i2c: bool,
) -> List[str]:
    """List features not actually verified by this run."""
    present = {suite.name.lower() for suite in suites if suite.tests}
    untested: List[str] = [
        "D0/RX and D1/TX were reserved for USB serial and not tested as general GPIO.",
        "GPIO drive strength, leakage, short-circuit behavior, and loaded-output performance were not measured.",
        "External interrupts and timer/counter accuracy were not tested.",
        "Power rails, current draw, regulator performance, clock accuracy, watchdog and reset-circuit behavior were not measured.",
        "EEPROM/flash write-integrity tests were intentionally omitted to avoid changing user data or firmware.",
        "External peripherals on UART or GPIO and all device-specific actuator/sensor behavior remain untested unless explicitly listed in results.",
    ]
    if "gpio" not in present:
        untested.append("Digital GPIO loopback on D2-D13 was not run.")
    if "adc" not in present:
        untested.append("ADC input checks on A0-A5 were not run.")
    else:
        untested.append("ADC linearity, reference-voltage accuracy and conversion timing were not calibrated.")
    if "pwm" not in present:
        untested.append("PWM output checks on D3, D5, D6, D9, D10 and D11 were not run.")
    else:
        untested.append("PWM frequency and duty cycle were not measured with a logic analyzer or oscilloscope.")
    if not scan_i2c:
        untested.append("I2C on A4/A5 was not scanned; connected I2C peripherals are unknown.")
    elif not identify_i2c:
        untested.append("I2C addresses may have ACKed, but known-device identity registers and device functions were not tested.")
    else:
        untested.append("Known I2C chip IDs may be identified; full sensor/display/module operation still requires device-specific tests.")
    if "spi" not in present:
        untested.append("SPI MOSI/MISO loopback on D11/D12 was not run.")
    else:
        untested.append("SPI external devices and full protocols were not tested; only the documented loopback was checked.")
    if "onboard" not in present:
        untested.append("The onboard L LED was not visually verified.")
    return untested


def _choose_port(
    requested_port: Optional[str],
    confirmed_board_id: Optional[str] = None,
) -> BoardDetection:
    detections = detect_connected_boards()
    exact_matches = [item for item in detections if item.profile_id == "arduino_uno_r3"]
    if requested_port:
        found = next(
            (item for item in detections if item.port.lower() == requested_port.lower()),
            None,
        )
        if found is None:
            raise RuntimeError("Serial port {} was not found.".format(requested_port))
        if found.profile_id == "arduino_uno_r3":
            if confirmed_board_id and confirmed_board_id != "arduino_uno_r3":
                raise RuntimeError(
                    "The USB identity matched Arduino Uno R3, so the requested manual "
                    "profile {} conflicts with detected evidence.".format(confirmed_board_id)
                )
            return found
        if confirmed_board_id == "arduino_uno_r3":
            # Explicit user choice lets a generic USB bridge be treated as a candidate,
            # but the MCU signature and diagnostic firmware handshake still must pass.
            return BoardDetection(
                port=found.port,
                description=found.description,
                hwid=found.hwid,
                vid=found.vid,
                pid=found.pid,
                profile_id="arduino_uno_r3",
                candidate_profile_id=found.candidate_profile_id,
                confidence="user_confirmed",
                match_method="explicit_user_confirmation",
                evidence=found.evidence + [
                    "User explicitly selected Arduino Uno R3; MCU signature and firmware handshake remain required."
                ],
            )
        raise RuntimeError(
            "Port {} does not have an exact Arduino Uno R3 USB profile match. "
            "For a known Uno clone only, specify --confirm-board arduino_uno_r3; "
            "signature and firmware checks will still be required.".format(requested_port)
        )
    if confirmed_board_id:
        raise RuntimeError("--confirm-board requires --port so the explicit choice is scoped to one device.")
    if len(exact_matches) == 1:
        return exact_matches[0]
    if not exact_matches:
        raise RuntimeError(
            "No exact Arduino Uno R3 USB identity detected. Connect a supported Uno R3 "
            "or use --port COMx --confirm-board arduino_uno_r3 for a known compatible clone."
        )
    raise RuntimeError(
        "More than one Uno R3 profile was detected; specify one with --port."
    )


def _read_startup(ser: serial.Serial, timeout_seconds: float = 8.0) -> List[str]:
    """Wait for the expected firmware banner after opening the serial port resets the Uno."""
    deadline = time.monotonic() + timeout_seconds
    lines: List[str] = []
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            lines.append(line)
        if _READY_MARKER in line:
            return lines
    return lines


def _send_command(
    ser: serial.Serial,
    command: str,
    terminal_markers: Sequence[str],
    timeout_seconds: float = 5.0,
) -> Tuple[List[str], float, bool]:
    """Send one newline-terminated command and read through a terminal marker."""
    ser.reset_input_buffer()
    started = time.monotonic()
    ser.write((command + "\n").encode("ascii"))
    ser.flush()
    deadline = time.monotonic() + timeout_seconds
    lines: List[str] = []
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            lines.append(line)
            if any(marker in line for marker in terminal_markers):
                return lines, (time.monotonic() - started) * 1000.0, True
    return lines, (time.monotonic() - started) * 1000.0, False


def _prompt_run(prompt: str) -> str:
    answer = input("{} [R=run, S=skip, Q=stop remaining manual tests]: ".format(prompt))
    normalized = answer.strip().lower()
    if normalized in {"r", "run", "ready", "y", "yes"}:
        return "run"
    if normalized in {"q", "quit", "stop"}:
        return "stop"
    return "skip"


def _add_skipped(test_results: List[TestResultData], name: str, suite: str, reason: str) -> None:
    test_results.append(_test_result(name, suite, "skip", reason))


def _run_manual_tests(
    ser: serial.Serial,
    gpio_tests: List[TestResultData],
    pwm_tests: List[TestResultData],
    adc_tests: List[TestResultData],
    spi_tests: List[TestResultData],
    led_tests: List[TestResultData],
    timeout_seconds: float,
) -> None:
    print()
    print("MANUAL HARDWARE TESTS")
    print("Disconnect shields/peripherals first. Only connect the jumper requested for each test.")
    ready = input("Type READY when all external wiring is removed and you can move one jumper safely: ")
    if ready.strip().lower() != "ready":
        reason = "User did not confirm safe wiring; test was not executed."
        _add_skipped(gpio_tests, "GPIO loopback series", "GPIO", reason)
        _add_skipped(pwm_tests, "PWM output series", "PWM", reason)
        _add_skipped(adc_tests, "ADC input series", "ADC", reason)
        _add_skipped(spi_tests, "SPI loopback", "SPI", reason)
        _add_skipped(led_tests, "Onboard LED visual check", "Onboard", reason)
        return

    stop = False
    action = _prompt_run("Run onboard LED blink test; observe the L LED")
    if action == "run":
        lines, elapsed, completed = _send_command(
            ser, "LED", ("LED test sequence complete",), timeout_seconds
        )
        observed = input("Did the onboard L LED blink three times? [y/n]: ").strip().lower()
        if observed in {"y", "yes"}:
            status = "pass" if completed else "fail"
        elif observed in {"n", "no"}:
            status = "fail"
        else:
            status = "skip"
        led_tests.append(_test_result(
            "Onboard LED blink",
            "Onboard",
            status,
            " | ".join(lines) if lines else "No LED result received.",
            elapsed,
        ))
    else:
        _add_skipped(
            led_tests, "Onboard LED blink", "Onboard",
            "User skipped the test." if action == "skip" else "User stopped remaining manual tests.",
        )
        stop = action == "stop"

    pairs = [(2, pin) for pin in range(3, 14)] + [(3, 4)]
    for source, sink in pairs:
        name = "GPIO jumper pair D{}-D{}".format(source, sink)
        if stop:
            _add_skipped(gpio_tests, name, "GPIO", "Skipped because the user stopped remaining manual tests.")
            continue
        action = _prompt_run(
            "Connect exactly one jumper D{} <-> D{}; run PAIR {} {}".format(
                source, sink, source, sink
            )
        )
        if action == "stop":
            stop = True
        if action != "run":
            _add_skipped(
                gpio_tests, name, "GPIO",
                "User stopped remaining manual tests." if stop else "User skipped; no measurement made.",
            )
            continue

        lines, elapsed, completed = _send_command(
            ser, "PAIR {} {}".format(source, sink), ("PAIR RESULT:",), timeout_seconds
        )
        direction_results = parse_pair_results(lines)
        if not completed or not direction_results:
            gpio_tests.append(_test_result(
                name, "GPIO", "fail",
                "No parseable PAIR result. Output: {}".format(" | ".join(lines)),
                elapsed,
            ))
        else:
            for direction_name, status, evidence_line in direction_results:
                gpio_tests.append(_test_result(
                    direction_name, "GPIO", status, evidence_line,
                    parse_firmware_duration(evidence_line),
                ))

    for pwm_pin in (3, 5, 6, 9, 10, 11):
        name = "PWM output D{}".format(pwm_pin)
        if stop:
            _add_skipped(pwm_tests, name, "PWM", "Skipped because the user stopped remaining manual tests.")
            continue
        action = _prompt_run(
            "Connect jumper D{} (PWM output) <-> D2 (input); run PWM {} 2".format(
                pwm_pin, pwm_pin
            )
        )
        if action == "stop":
            stop = True
        if action != "run":
            _add_skipped(
                pwm_tests, name, "PWM",
                "User stopped remaining manual tests." if stop else "User skipped; no measurement made.",
            )
            continue

        lines, elapsed, completed = _send_command(
            ser, "PWM {} 2".format(pwm_pin), ("PWM RESULT:",), timeout_seconds
        )
        result_line = next((line for line in lines if "PWM RESULT:" in line), "")
        status = "pass" if completed and "PWM RESULT: PASS" in result_line else "fail"
        pwm_tests.append(_test_result(
            name, "PWM", status,
            result_line or "No PWM result received. Output: {}".format(" | ".join(lines)),
            parse_firmware_duration(result_line),
        ))

    for analog_index in range(6):
        for level, rail in (("LOW", "GND"), ("HIGH", "5V")):
            name = "ADC A{} {}".format(analog_index, level)
            if stop:
                _add_skipped(adc_tests, name, "ADC", "Skipped because the user stopped remaining manual tests.")
                continue
            action = _prompt_run(
                "Connect A{} to {} only (never bridge 5V to GND); run ADC A{} {}".format(
                    analog_index, rail, analog_index, level
                )
            )
            if action == "stop":
                stop = True
            if action != "run":
                _add_skipped(
                    adc_tests, name, "ADC",
                    "User stopped remaining manual tests." if stop else "User skipped; no measurement made.",
                )
                continue

            lines, elapsed, completed = _send_command(
                ser, "ADC A{} {}".format(analog_index, level),
                ("=> PASS", "=> FAIL", "ERROR:"), timeout_seconds,
            )
            result_line = next(
                (line for line in lines if line.startswith("ADC A{} ".format(analog_index))),
                "",
            )
            status = "pass" if completed and result_line.endswith("=> PASS") else "fail"
            if "ERROR:" in result_line:
                status = "fail"
            adc_value = parse_adc_measurement(result_line)
            measurements = [float(adc_value)] if adc_value is not None else []
            adc_tests.append(_test_result(
                name, "ADC", status,
                result_line or "No ADC result received. Output: {}".format(" | ".join(lines)),
                parse_firmware_duration(result_line), measurements,
            ))

    if stop:
        _add_skipped(
            spi_tests, "SPI MOSI/MISO loopback", "SPI",
            "Skipped because the user stopped remaining manual tests.",
        )
        return

    action = _prompt_run("Connect D11 MOSI <-> D12 MISO; disconnect external SPI devices")
    if action == "run":
        lines, elapsed, completed = _send_command(
            ser, "SPI_LOOPBACK", ("SPI_LOOPBACK RESULT:",), timeout_seconds
        )
        result_line = next((line for line in lines if "SPI_LOOPBACK RESULT:" in line), "")
        status = "pass" if completed and "SPI_LOOPBACK RESULT: PASS" in result_line else "fail"
        spi_tests.append(_test_result(
            "SPI MOSI/MISO loopback", "SPI", status,
            result_line or "No SPI result received. Output: {}".format(" | ".join(lines)),
            elapsed,
        ))
    else:
        _add_skipped(
            spi_tests, "SPI MOSI/MISO loopback", "SPI",
            "User stopped remaining manual tests." if action == "stop" else "User skipped; no measurement made.",
        )

def _record_unexecuted_manual_groups(
    gpio_tests: List[TestResultData],
    pwm_tests: List[TestResultData],
    adc_tests: List[TestResultData],
    spi_tests: List[TestResultData],
    led_tests: List[TestResultData],
    reason: str,
) -> None:
    """Record unfinished manual groups so missing coverage is visible in reports."""
    _add_skipped(led_tests, "Remaining onboard LED check", "Onboard", reason)
    _add_skipped(gpio_tests, "Remaining GPIO loopback checks", "GPIO", reason)
    _add_skipped(pwm_tests, "Remaining PWM output checks", "PWM", reason)
    _add_skipped(adc_tests, "Remaining ADC input checks", "ADC", reason)
    _add_skipped(spi_tests, "SPI MOSI/MISO loopback", "SPI", reason)


def run_diagnostic(
    detection: BoardDetection,
    output_dir: Path,
    interactive: bool = False,
    scan_i2c: bool = False,
    identify_i2c: bool = False,
    ai_analysis: bool = False,
    nemotron_model: Optional[str] = None,
    external_observations_path: Optional[Path] = None,
    check_signature: bool = True,
    avrdude_executable: Optional[Path] = None,
    avrdude_config: Optional[Path] = None,
    timeout_seconds: float = 5.0,
) -> DiagnosticReport:
    """Run the already-uploaded Uno diagnostic sketch and generate reports."""
    profile = detection.profile
    if profile is None or profile.board_id != "arduino_uno_r3":
        raise RuntimeError("The Uno serial adapter requires an exact Arduino Uno R3 profile match.")

    start_time = time.perf_counter()
    host_tests = [
        _test_result(
            "USB serial board identity",
            "Host interface",
            "pass",
            "Exact USB VID/PID match for {} on {}.".format(profile.display_name, detection.port),
        )
    ]
    firmware_tests: List[TestResultData] = []
    chip_tests: List[TestResultData] = []
    led_tests: List[TestResultData] = []
    gpio_tests: List[TestResultData] = []
    pwm_tests: List[TestResultData] = []
    adc_tests: List[TestResultData] = []
    spi_tests: List[TestResultData] = []
    i2c_tests: List[TestResultData] = []
    external = load_external_observations(external_observations_path)

    if check_signature:
        signature_status, signature_details, signature_elapsed = read_atmega328p_signature(
            detection.port,
            executable=avrdude_executable,
            config_file=avrdude_config,
        )
        chip_tests.append(_test_result(
            "ATmega328P device signature",
            "Chip identification",
            signature_status,
            signature_details,
            signature_elapsed,
        ))
    else:
        signature_status = "skip"
        chip_tests.append(_test_result(
            "ATmega328P device signature",
            "Chip identification",
            "skip",
            "Skipped by the user; MCU silicon signature was not independently verified.",
        ))

    if signature_status != "fail":
        try:
            with serial.Serial(detection.port, baudrate=115200, timeout=0.2, write_timeout=2.0) as ser:
                startup_lines = _read_startup(ser)
                if _READY_MARKER not in "\n".join(startup_lines):
                    raise RuntimeError(
                        "Expected the project diagnostic firmware banner was not received. "
                        "No diagnostic command was sent. Upload firmware/arduino_uno_r3/arduino_uno_r3.ino "
                        "manually, close Serial Monitor, and retry."
                    )

                lines, elapsed, completed = _send_command(
                    ser, "INFO", (_INFO_MARKER,), timeout_seconds
                )
                info = "\n".join(lines)
                if not completed or "BOARD:ARDUINO_UNO_R3" not in info or "FIRMWARE_VERSION:3" not in info:
                    raise RuntimeError(
                        "The port is an Uno R3, but it did not confirm diagnostic firmware version 3. "
                        "No other tests were run."
                    )
                firmware_tests.append(_test_result(
                    "Diagnostic firmware identity",
                    "Firmware handshake",
                    "pass",
                    info,
                    elapsed,
                ))

                if scan_i2c:
                    i2c_confirm = input(
                        "I2C scan sends address probes on A4/A5. Confirm any attached modules use "
                        "compatible voltage levels/pull-ups. Type SCAN to continue: "
                    )
                    if i2c_confirm.strip().upper() == "SCAN":
                        lines, elapsed, completed = _send_command(
                            ser, "I2C_SCAN", ("I2C_SCAN RESULT:",), timeout_seconds * 3
                        )
                        scan_line = next((line for line in lines if "I2C_SCAN RESULT:" in line), "")
                        addresses = parse_i2c_addresses(lines)
                        status = "pass" if completed and scan_line else "fail"
                        details = scan_line or "I2C scan timed out. Output: {}".format(" | ".join(lines))
                        i2c_tests.append(_test_result("I2C address scan", "I2C", status, details, elapsed))
                        for address in addresses:
                            matched_profile = None
                            matched_value = None
                            identity_evidence = []
                            candidate_profiles = profiles_for_i2c_address(address) if identify_i2c else []
                            registers = sorted({profile.identity_register for profile in candidate_profiles})
                            for register in registers:
                                read_lines, read_elapsed, read_completed = _send_command(
                                    ser,
                                    "I2C_READ 0x{:02X} 0x{:02X}".format(address, register),
                                    ("I2C_READ RESULT:", "ERROR:"),
                                    timeout_seconds,
                                )
                                read_line = next(
                                    (line for line in read_lines if "I2C_READ RESULT:" in line), ""
                                )
                                value_match = re.search(r"VALUE=0x([0-9A-F]{1,2})$", read_line, re.IGNORECASE)
                                value = int(value_match.group(1), 16) if value_match else None
                                if read_line:
                                    identity_evidence.append(read_line)
                                if read_completed and value is not None:
                                    candidate = match_i2c_identity(address, register, value)
                                    if candidate is not None:
                                        matched_profile = candidate
                                        matched_value = value
                                        i2c_tests.append(_test_result(
                                            "{} chip identity at 0x{:02X}".format(candidate.display_name, address),
                                            "I2C",
                                            "pass",
                                            read_line + " matched " + candidate.profile_id,
                                            read_elapsed,
                                            [float(value)],
                                        ))
                                        break

                            if matched_profile is not None:
                                external.append({
                                    "name": matched_profile.display_name,
                                    "interface": "I2C",
                                    "profile": matched_profile.profile_id,
                                    "status": "not_tested",
                                    "expected": "Device-specific functional checks beyond chip ID",
                                    "observed": (
                                        "ACK at 0x{:02X}; identity register 0x{:02X} returned 0x{:02X}."
                                        .format(address, matched_profile.identity_register, matched_value)
                                    ),
                                    "measurements": {},
                                    "evidence": [
                                        "Arduino Uno R3 I2C scanner reported ACK at this address."
                                    ] + identity_evidence,
                                    "notes": (
                                        "Device model was identified by its documented ID register. "
                                        "Its sensor/display/actuator functions were not yet tested."
                                    ),
                                })
                            else:
                                external.append({
                                    "name": "Unidentified I2C peripheral at 0x{:02X}".format(address),
                                    "interface": "I2C",
                                    "profile": "",
                                    "status": "unknown",
                                    "expected": "Device-specific identity/health test",
                                    "observed": "Address 0x{:02X} acknowledged an I2C address probe.".format(address),
                                    "measurements": {},
                                    "evidence": [
                                        "Arduino Uno R3 I2C scanner reported ACK at this address."
                                    ] + identity_evidence,
                                    "notes": (
                                        "No known ID-register profile matched. Address ACK does not "
                                        "identify the device or prove it is healthy."
                                    ),
                                })
                        if not addresses and status == "pass":
                            i2c_tests[-1].details += " No peripherals ACKed; this is not by itself an MCU failure."
                    else:
                        _add_skipped(i2c_tests, "I2C address scan", "I2C", "User did not approve I2C bus scan.")
                if interactive:
                    _run_manual_tests(
                        ser, gpio_tests, pwm_tests, adc_tests, spi_tests, led_tests, timeout_seconds
                    )
        except serial.SerialException as exc:
            detail = (
                "Could not open/use {}. Close Arduino Serial Monitor and other serial applications. ({})"
                .format(detection.port, exc)
            )
            host_tests.append(_test_result(
                "Serial connection to diagnostic firmware",
                "Host interface",
                "fail",
                detail,
            ))
            if not firmware_tests:
                _add_skipped(
                    firmware_tests,
                    "Diagnostic firmware identity",
                    "Firmware handshake",
                    "Skipped because the diagnostic serial connection could not be used.",
                )
            if scan_i2c and not i2c_tests:
                _add_skipped(i2c_tests, "I2C address scan", "I2C", detail)
            if interactive:
                _record_unexecuted_manual_groups(
                    gpio_tests, pwm_tests, adc_tests, spi_tests, led_tests, detail
                )
        except RuntimeError as exc:
            detail = str(exc)
            firmware_tests.append(_test_result(
                "Diagnostic firmware handshake",
                "Firmware handshake",
                "fail",
                detail,
            ))
            if scan_i2c and not i2c_tests:
                _add_skipped(i2c_tests, "I2C address scan", "I2C", detail)
            if interactive:
                _record_unexecuted_manual_groups(
                    gpio_tests, pwm_tests, adc_tests, spi_tests, led_tests,
                    "Skipped because the diagnostic firmware handshake failed.",
                )
    else:
        reason = (
            "Skipped because the AVRDUDE MCU signature check did not match the expected "
            "ATmega328P signature. No serial sketch commands were sent."
        )
        _add_skipped(firmware_tests, "Diagnostic firmware identity", "Firmware handshake", reason)
        if scan_i2c:
            _add_skipped(i2c_tests, "I2C address scan", "I2C", reason)
        if interactive:
            _add_skipped(led_tests, "Onboard LED blink", "Onboard", reason)
            for source, sink in ([(2, pin) for pin in range(3, 14)] + [(3, 4)]):
                _add_skipped(gpio_tests, "GPIO jumper pair D{}-D{}".format(source, sink), "GPIO", reason)
            for pin in (3, 5, 6, 9, 10, 11):
                _add_skipped(pwm_tests, "PWM output D{}".format(pin), "PWM", reason)
            for pin in range(6):
                for level in ("LOW", "HIGH"):
                    _add_skipped(adc_tests, "ADC A{} {}".format(pin, level), "ADC", reason)
            _add_skipped(spi_tests, "SPI MOSI/MISO loopback", "SPI", reason)

    suites: List[SuiteResultData] = []
    for name, tests in (
        ("Host interface", host_tests),
        ("Chip identification", chip_tests),
        ("Firmware handshake", firmware_tests),
        ("Onboard", led_tests),
        ("GPIO", gpio_tests),
        ("PWM", pwm_tests),
        ("ADC", adc_tests),
        ("SPI", spi_tests),
        ("I2C", i2c_tests),
    ):
        if tests:
            suites.append(_make_suite(name, tests))

    test_suites = [suite.name.lower().replace(" ", "-") for suite in suites]
    report = DiagnosticReport(
        mcu_family=profile.mcu_family,
        mcu_part="{} ({})".format(profile.display_name, profile.mcu_part),
        test_suites=test_suites,
        suites=suites,
        external_peripherals=external,
        duration=time.perf_counter() - start_time,
        firmware_version=3,
        device_id=(
            detection.hwid
            or "USB:{:04X}:{:04X}@{}".format(detection.vid or 0, detection.pid or 0, detection.port)
        ),
        untested_peripherals=_derive_untested_features(suites, scan_i2c, identify_i2c),
    )

    if ai_analysis:
        try:
            report.ai_analysis = generate_ai_analysis(
                asdict(report),
                model=nemotron_model,
            )
        except Exception as exc:
            report.ai_analysis = (
                "AI analysis unavailable. No AI-generated cause or repair advice was produced. "
                "Reason: {}: {}".format(type(exc).__name__, exc)
            )

    ReportGenerator(output_dir).generate(report)
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the board-specific diagnostic sketch on an Arduino Uno R3."
    )
    parser.add_argument("--port", help="Serial port (e.g. COM9); auto-selects only if exactly one Uno R3 is detected.")
    parser.add_argument("--confirm-board", choices=["arduino_uno_r3"], help="Explicitly select the Uno profile for a known clone with an unrecognized USB bridge; still requires chip signature and firmware identity checks.")
    parser.add_argument("--output", default="./results/arduino_uno_r3", help="Directory for TXT/HTML/JSON reports.")
    parser.add_argument("--interactive", action="store_true", help="Run GPIO, PWM, ADC, LED and SPI tests with jumper prompts.")
    parser.add_argument("--scan-i2c", action="store_true", help="Scan I2C addresses after explicit voltage/wiring confirmation.")
    parser.add_argument("--identify-i2c", action="store_true", help="Also read documented ID registers for known supported sensors; implies --scan-i2c.")
    parser.add_argument("--ai-analysis", action="store_true", help="Add optional NVIDIA Nemotron analysis to reports.")
    parser.add_argument("--nemotron-model", default=None, help="Optional NVIDIA NIM model identifier.")
    parser.add_argument("--external-observations", help="JSON file with separately recorded peripheral evidence.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for each firmware command response.")
    parser.add_argument("--skip-signature-check", action="store_true", help="Skip AVRDUDE MCU signature verification.")
    parser.add_argument("--avrdude-path", help="Optional path to avrdude.exe/avrdude for chip signature verification.")
    parser.add_argument("--avrdude-config", help="Optional path to avrdude.conf.")
    parser.add_argument("--yes-reset", action="store_true", help="Confirm the serial port may auto-reset the Uno when opened.")
    args = parser.parse_args(argv)

    try:
        detection = _choose_port(args.port, args.confirm_board)
        print(
            "Detected {} ({}) on {} using exact USB identity.".format(
                detection.profile.display_name, detection.profile.mcu_part, detection.port
            )
        )
        print("This runner does not upload firmware. AVRDUDE signature checks and opening the serial port may reset the board.")
        if not args.yes_reset:
            confirmation = input("Type RESET to continue; anything else cancels: ")
            if confirmation.strip().upper() != "RESET":
                print("Cancelled; no serial port opened.")
                return 0

        report = run_diagnostic(
            detection=detection,
            output_dir=Path(args.output),
            interactive=args.interactive,
            scan_i2c=args.scan_i2c or args.identify_i2c,
            identify_i2c=args.identify_i2c,
            ai_analysis=args.ai_analysis,
            nemotron_model=args.nemotron_model,
            external_observations_path=(
                Path(args.external_observations) if args.external_observations else None
            ),
            check_signature=not args.skip_signature_check,
            avrdude_executable=Path(args.avrdude_path) if args.avrdude_path else None,
            avrdude_config=Path(args.avrdude_config) if args.avrdude_config else None,
            timeout_seconds=args.timeout,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        print("Diagnostic runner stopped safely: {}".format(exc), file=sys.stderr)
        return 2

    print()
    print("=== Arduino Uno R3 Diagnostic Complete ===")
    print("Tests: {} ({} passed, {} failed, {} skipped)".format(
        report.total_tests, report.passed, report.failed, report.skipped
    ))
    if report.external_peripherals:
        print("External observations: {} (not necessarily identified or fully tested)".format(
            len(report.external_peripherals)
        ))
    print("Text report: {}".format(report.report_path))
    print("HTML report: {}".format(report.html_path))
    print("JSON report: {}".format(report.json_path))
    if report.failed or report.external_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
