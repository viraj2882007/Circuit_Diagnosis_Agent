"""Load and validate observations recorded by external peripheral tests/adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALLOWED_STATUSES = {"pass", "fail", "warning", "unknown", "not_tested"}
_MAX_FILE_BYTES = 1_000_000


def _short_text(value: Any, limit: int = 700) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    return str(value)[:limit]


def load_external_observations(path: Path | str | None) -> list[dict[str, Any]]:
    """Return normalized external peripheral observations from an optional JSON file.

    Expected shape: {"board": "...", "peripherals": [{"name": "...", "status": "..."}]}.
    This function validates recorded evidence; it does not probe hardware by itself.
    """
    if path is None:
        return []
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"External observation file not found: {source}")
    if source.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("External observation JSON exceeds the 1 MB safety limit.")

    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read external observation JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError("External observation JSON must be an object.")
    raw_peripherals = document.get("peripherals")
    if not isinstance(raw_peripherals, list):
        raise ValueError("External observation JSON must contain a 'peripherals' array.")
    if len(raw_peripherals) > 200:
        raise ValueError("External observation JSON may contain at most 200 peripherals.")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_peripherals):
        if not isinstance(item, dict):
            raise ValueError(f"Peripheral entry {index} must be a JSON object.")
        name = _short_text(item.get("name"), 160).strip()
        if not name:
            raise ValueError(f"Peripheral entry {index} needs a non-empty 'name'.")
        status = _short_text(item.get("status", "unknown"), 32).strip().lower()
        if status not in _ALLOWED_STATUSES:
            allowed = ", ".join(sorted(_ALLOWED_STATUSES))
            raise ValueError(f"Invalid status for '{name}': {status!r}. Allowed: {allowed}.")
        measurements = item.get("measurements", {})
        if not isinstance(measurements, (dict, list, str, int, float, type(None))):
            measurements = _short_text(measurements)
        evidence = item.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list):
            evidence = [_short_text(evidence)]
        normalized.append({
            "name": name,
            "interface": _short_text(item.get("interface", "unspecified"), 80),
            "profile": _short_text(item.get("profile", ""), 80),
            "status": status,
            "expected": _short_text(item.get("expected"), 500),
            "observed": _short_text(item.get("observed"), 500),
            "measurements": measurements,
            "evidence": [_short_text(line, 700) for line in evidence[:30]],
            "notes": _short_text(item.get("notes"), 1000),
        })
    return normalized
