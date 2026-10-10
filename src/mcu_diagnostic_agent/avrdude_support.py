"""Safe AVR device-signature reads using AVRDUDE.

The command uses AVRDUDE's no-write option. Reading a signature may reset a board,
but this module never uploads firmware or issues erase/write commands.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple


def _search_roots() -> List[Path]:
    roots: List[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "Arduino15")
    roots.extend([
        Path.home() / "Library" / "Arduino15",
        Path.home() / ".arduino15",
        Path.home() / "AppData" / "Local" / "Arduino15",
        Path("/usr/share/arduino"),
        Path("/opt/arduino"),
        Path("/Applications/Arduino IDE.app"),
    ])
    return [root for root in roots if root.exists()]


def locate_avrdude(
    executable: Optional[Path] = None,
    config_file: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path], str]:
    """Find AVRDUDE and its config file, preferring an explicitly supplied path."""
    binary: Optional[Path] = None
    if executable is not None:
        candidate = Path(executable).expanduser()
        if not candidate.is_file():
            return None, None, "Configured AVRDUDE executable does not exist: {}".format(candidate)
        binary = candidate
    else:
        found_on_path = shutil.which("avrdude") or shutil.which("avrdude.exe")
        if found_on_path:
            binary = Path(found_on_path)
        else:
            for root in _search_roots():
                matches = list(root.rglob("avrdude.exe")) + list(root.rglob("avrdude"))
                binaries = [path for path in matches if path.is_file()]
                if binaries:
                    # Prefer the Arduino package layout whose config sits beside the binary.
                    binary = sorted(binaries, key=lambda path: len(str(path)))[0]
                    break

    if binary is None:
        return None, None, "AVRDUDE was not found; MCU signature check skipped."

    if config_file is not None:
        config = Path(config_file).expanduser()
        if not config.is_file():
            return binary, None, "AVRDUDE config file does not exist: {}".format(config)
        return binary, config, ""

    config_candidates = [
        binary.parent.parent / "etc" / "avrdude.conf",
        binary.parent / "avrdude.conf",
    ]
    for root in _search_roots():
        config_candidates.extend(root.rglob("avrdude.conf"))
    for candidate in config_candidates:
        if candidate.is_file():
            return binary, candidate, ""

    return binary, None, "AVRDUDE was found, but avrdude.conf could not be located."


def parse_device_signature(output: str) -> Optional[str]:
    """Extract a three-byte AVRDUDE device signature from command output."""
    match = re.search(
        r"Device signature\s*=\s*([0-9A-Fa-f]{2}\s+[0-9A-Fa-f]{2}\s+[0-9A-Fa-f]{2})",
        output,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return " ".join(match.group(1).upper().split())


def read_atmega328p_signature(
    port: str,
    executable: Optional[Path] = None,
    config_file: Optional[Path] = None,
    timeout_seconds: float = 20.0,
) -> Tuple[str, str, float]:
    """Return pass/fail/skip, evidence details, and elapsed milliseconds.

    Only the ATmega328P signature is accepted as a pass. AVRDUDE is run with -n
    and without any write/erase operations.
    """
    binary, config, discovery_message = locate_avrdude(executable, config_file)
    if binary is None or config is None:
        return "skip", discovery_message, 0.0

    command = [
        str(binary),
        "-C", str(config),
        "-v",
        "-n",
        "-p", "atmega328p",
        "-c", "arduino",
        "-P", port,
        "-b", "115200",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - started) * 1000.0
        return "fail", "AVRDUDE signature read timed out after {:.1f}s.".format(timeout_seconds), elapsed
    except OSError as exc:
        elapsed = (time.monotonic() - started) * 1000.0
        return "fail", "Could not launch AVRDUDE: {}".format(exc), elapsed

    elapsed = (time.monotonic() - started) * 1000.0
    signature = parse_device_signature(completed.stdout)
    if completed.returncode == 0 and signature == "1E 95 0F":
        return "pass", "AVRDUDE read expected ATmega328P signature 1E 95 0F with no-write mode.", elapsed
    if signature is not None:
        return "fail", "Unexpected AVR device signature {} (expected 1E 95 0F).".format(signature), elapsed

    tail = "\n".join(completed.stdout.splitlines()[-8:])
    return "fail", "AVRDUDE could not verify the ATmega328P signature. {}".format(tail), elapsed
