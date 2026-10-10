"""Conservative USB serial board discovery CLI.

This module only enumerates host serial ports and matches known profiles. It does
not reset, flash, or send commands to a connected device.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from serial.tools import list_ports

from .board_profiles import (
    BOARD_PROFILES,
    BoardProfile,
    build_diagnostic_plan,
    find_profiles_by_usb_id,
)


@dataclass(frozen=True)
class BoardDetection:
    """One serial-port observation and its board-identification confidence."""

    port: str
    description: str
    hwid: str
    vid: Optional[int]
    pid: Optional[int]
    profile_id: Optional[str]
    candidate_profile_id: Optional[str]
    confidence: str
    match_method: str
    evidence: List[str]

    @property
    def recognized(self) -> bool:
        """Whether an exact, configured identifier match was found."""
        return self.profile_id is not None

    @property
    def profile(self) -> Optional[BoardProfile]:
        """Return the exact matched profile, if any."""
        if self.profile_id is None:
            return None
        return BOARD_PROFILES[self.profile_id]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable detection record."""
        data = asdict(self)
        data["recognized"] = self.recognized
        data["vid_pid"] = (
            "{:04X}:{:04X}".format(self.vid, self.pid)
            if self.vid is not None and self.pid is not None
            else None
        )
        if self.profile is not None:
            data["profile"] = self.profile.to_dict()
        else:
            data["profile"] = None
        if self.candidate_profile_id:
            data["candidate_profile"] = BOARD_PROFILES[self.candidate_profile_id].to_dict()
        else:
            data["candidate_profile"] = None
        return data


def _normalise_text(value: Any) -> str:
    """Normalize descriptive USB metadata for conservative hint matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            try:
                return int(value, 16)
            except ValueError:
                return None
    return None


def detect_connected_boards(ports: Optional[Iterable[Any]] = None) -> List[BoardDetection]:
    """Enumerate serial ports and identify only profiles with exact known USB IDs.

    Description-only matches are returned as low-confidence candidates and must
    not be used to select a test plan automatically. Passing a port collection is
    intended for deterministic tests and callers that already enumerated ports.
    """
    port_items = list(list_ports.comports() if ports is None else ports)
    detections: List[BoardDetection] = []

    for item in port_items:
        port = str(getattr(item, "device", "") or "")
        description = str(getattr(item, "description", "") or "")
        hwid = str(getattr(item, "hwid", "") or "")
        vid = _as_int(getattr(item, "vid", None))
        pid = _as_int(getattr(item, "pid", None))
        product = str(getattr(item, "product", "") or "")
        manufacturer = str(getattr(item, "manufacturer", "") or "")
        searchable = _normalise_text(" ".join((description, product, manufacturer)))
        exact = find_profiles_by_usb_id(vid, pid)

        if len(exact) == 1:
            profile = exact[0]
            evidence = ["Exact configured USB VID/PID {:04X}:{:04X}".format(vid, pid)]
            if description:
                evidence.append("USB description: {}".format(description))
            detections.append(BoardDetection(
                port=port,
                description=description,
                hwid=hwid,
                vid=vid,
                pid=pid,
                profile_id=profile.board_id,
                candidate_profile_id=None,
                confidence="high",
                match_method="exact_usb_vid_pid",
                evidence=evidence,
            ))
            continue

        hinted: List[BoardProfile] = []
        for profile in BOARD_PROFILES.values():
            if any(_normalise_text(hint) in searchable for hint in profile.description_hints):
                hinted.append(profile)

        candidate = hinted[0] if len(hinted) == 1 else None
        evidence = []
        if vid is not None and pid is not None:
            evidence.append("Unmatched USB VID/PID {:04X}:{:04X}".format(vid, pid))
        if description:
            evidence.append("USB description: {}".format(description))
        if candidate is not None:
            evidence.append("Name/description hint only; board identity is not confirmed")
        else:
            evidence.append("No exact board profile match")

        detections.append(BoardDetection(
            port=port,
            description=description,
            hwid=hwid,
            vid=vid,
            pid=pid,
            profile_id=None,
            candidate_profile_id=candidate.board_id if candidate else None,
            confidence="low" if candidate else "unknown",
            match_method="description_hint" if candidate else "unrecognized",
            evidence=evidence,
        ))

    return detections


def detect_connected_debug_probes() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """List recognizable debug-probe USB devices without connecting to the target MCU.

    A probe listing is not a target-MCU identification. Target identification needs
    a probe-specific target-ID operation and appropriate target selection.
    """
    try:
        from .probe.factory import ProbeFactory

        return ProbeFactory().detect_probes(), None
    except Exception as exc:
        return [], "Debug-probe inventory unavailable: {}: {}".format(type(exc).__name__, exc)


def _format_probe_id(value: Any) -> str:
    if isinstance(value, int):
        return "{:04X}".format(value)
    text = str(value or "").strip()
    return text.upper() if text else "????"


def _print_detections(detections: List[BoardDetection], debug_probes: List[Dict[str, Any]], probe_error: Optional[str] = None) -> None:
    print("Board discovery (read-only; no reset, firmware upload, or hardware tests performed)")
    print("=" * 78)
    for detection in detections:
        usb_id = (
            "{:04X}:{:04X}".format(detection.vid, detection.pid)
            if detection.vid is not None and detection.pid is not None
            else "unknown VID:PID"
        )
        if detection.profile is not None:
            print(
                "{}: {} ({}) - HIGH confidence via {} [{}]".format(
                    detection.port,
                    detection.profile.display_name,
                    detection.profile.mcu_part,
                    detection.match_method,
                    usb_id,
                )
            )
            print("  This identifies a known USB interface; it does not prove the board is healthy.")
        elif detection.candidate_profile_id is not None:
            profile = BOARD_PROFILES[detection.candidate_profile_id]
            print(
                "{}: possible {} - LOW confidence; not auto-selected [{}]".format(
                    detection.port, profile.display_name, usb_id
                )
            )
        else:
            print(
                "{}: unknown board - no profile selected [{}]".format(
                    detection.port, usb_id
                )
            )
        print("  {}".format(detection.description or detection.hwid or "No descriptor available"))

    if not detections:
        print("No USB serial ports found.")

    print()
    print("Debug probes (probe presence does not identify the target MCU):")
    if debug_probes:
        for probe in debug_probes:
            print(
                "- {type} {product} VID:PID={vid}:{pid} serial={serial} backend={backend}".format(
                    type=probe.get("type", "debug probe"),
                    product=probe.get("product") or "unknown product",
                    vid=_format_probe_id(probe.get("vid")),
                    pid=_format_probe_id(probe.get("pid")),
                    serial=probe.get("serial") or "unknown",
                    backend=probe.get("backend") or "unknown",
                )
            )
        print("Target MCU identification still requires a supported target-ID adapter.")
    elif probe_error:
        print(probe_error)
    else:
        print("No supported debug probes detected.")

    print()
    print("Known profiles: {}".format(", ".join(
        profile.display_name for profile in BOARD_PROFILES.values()
    )))
    print("A serial test plan can only be printed for an exact profile match, e.g. --plan COM9.")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for passive board discovery and plan preview."""
    parser = argparse.ArgumentParser(
        description="Identify supported USB serial boards and preview safe test plans."
    )
    parser.add_argument(
        "--plan",
        metavar="PORT",
        help="Print a board-specific test plan for a port with an exact profile match (e.g. COM9).",
    )
    parser.add_argument(
        "--include-destructive",
        action="store_true",
        help="Show memory-write test requirements in the plan; does not execute them.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the human-readable summary.",
    )
    args = parser.parse_args(argv)

    try:
        detections = detect_connected_boards()
    except Exception as exc:
        print("Board discovery failed: {}".format(exc), file=sys.stderr)
        return 2
    debug_probes, probe_error = detect_connected_debug_probes()

    if args.plan:
        requested_port = args.plan.strip().lower()
        detection = next(
            (item for item in detections if item.port.lower() == requested_port),
            None,
        )
        if detection is None:
            message = "Port {!r} was not found in the current serial-port list.".format(args.plan)
            print(message, file=sys.stderr)
            if args.json:
                print(json.dumps({"error": "port_not_found", "ports": [d.to_dict() for d in detections]}, indent=2))
            return 2
        if detection.profile is None:
            message = (
                "No exact board profile match for {}. Refusing to guess a test plan. "
                "Detected candidate: {}. Select/confirm a profile explicitly before testing."
            ).format(args.plan, detection.candidate_profile_id or "none")
            if args.json:
                print(json.dumps({"error": "profile_not_confirmed", "detection": detection.to_dict()}, indent=2))
            else:
                print(message, file=sys.stderr)
            return 2

        plan = build_diagnostic_plan(detection.profile, include_destructive=args.include_destructive)
        plan["detection"] = detection.to_dict()
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print("Board: {} ({})".format(plan["board"]["display_name"], plan["board"]["mcu_part"]))
            print("Plan only: no tests executed and no hardware changed.")
            print(
                "Execution adapter: {}".format(
                    "available" if plan["adapter"]["implementation_available"] else "not implemented yet"
                )
            )
            print(plan["adapter"]["note"])
            print(plan["warning"])
            print()
            for test in plan["tests"]:
                print("[{}] {} - {}".format(test["status"].upper(), test["id"], test["description"]))
                for requirement in test.get("prerequisites", []):
                    print("  - {}".format(requirement))
            print()
            print("Profile capabilities are not test results. Only completed measurements can yield PASS/FAIL.")
        return 0

    if args.json:
        print(json.dumps({
            "serial_board_detections": [item.to_dict() for item in detections],
            "debug_probes": debug_probes,
            "debug_probe_detection_error": probe_error,
            "note": "Detected debug probes are not proof of target MCU identity or hardware health.",
        }, indent=2))
    else:
        _print_detections(detections, debug_probes, probe_error)
    return 0 if detections or debug_probes else 1


if __name__ == "__main__":
    raise SystemExit(main())
