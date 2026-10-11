"""Evaluate reviewed fault-injection cases without pretending unreviewed outcomes are correct.

Input records represent faults physically or in a fixture deliberately injected by a tester.
This module scores the diagnostic result after a human compares it with the known ground truth;
it does not inject faults or communicate with hardware.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_MAX_FILE_BYTES = 5_000_000
_MAX_CASES = 10_000
_ASSESSMENTS = {"correct", "incorrect", "missed", "inconclusive", "unreviewed"}


def evaluate_fault_cases(document: dict[str, Any]) -> dict[str, Any]:
    """Compute fault-identification accuracy from reviewed, explicitly injected cases.

    The headline metric is correctly identified injected faults / all injected faults.
    Unreviewed cases remain in the denominator and therefore cannot inflate accuracy.
    """
    if not isinstance(document, dict):
        raise ValueError("Fault-evaluation input must be a JSON object.")
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Fault-evaluation JSON must contain a 'cases' array.")
    if not cases:
        raise ValueError("At least one injected fault case is required.")
    if len(cases) > _MAX_CASES:
        raise ValueError("At most {} cases may be evaluated.".format(_MAX_CASES))

    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError("Case {} must be a JSON object.".format(index))
        case_id = str(case.get("case_id", "")).strip()
        fault_id = str(case.get("fault_id", "")).strip()
        injected_fault = str(case.get("injected_fault", "")).strip()
        if not case_id:
            raise ValueError("Case {} needs a non-empty case_id.".format(index))
        if case_id in ids:
            raise ValueError("Duplicate case_id: {}".format(case_id))
        ids.add(case_id)
        if not fault_id or not injected_fault:
            raise ValueError(
                "Case {!r} needs non-empty fault_id and injected_fault.".format(case_id)
            )
        assessment = str(case.get("assessment", "unreviewed")).strip().lower()
        if assessment not in _ASSESSMENTS:
            raise ValueError(
                "Invalid assessment for {!r}: {!r}. Allowed: {}.".format(
                    case_id, assessment, ", ".join(sorted(_ASSESSMENTS))
                )
            )
        normalized.append({
            "case_id": case_id,
            "fault_id": fault_id,
            "injected_fault": injected_fault,
            "expected_diagnosis": str(case.get("expected_diagnosis", ""))[:2000],
            "observed_diagnosis": str(case.get("observed_diagnosis", ""))[:4000],
            "assessment": assessment,
            "reviewer_note": str(case.get("reviewer_note", ""))[:2000],
            "report_path": str(case.get("report_path", ""))[:1000],
        })

    total = len(normalized)
    correct = sum(case["assessment"] == "correct" for case in normalized)
    reviewed = sum(case["assessment"] != "unreviewed" for case in normalized)
    counts = {status: sum(case["assessment"] == status for case in normalized)
              for status in sorted(_ASSESSMENTS)}

    by_fault: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in normalized:
        by_fault[case["fault_id"]].append(case)
    per_fault = []
    for fault_id, rows in sorted(by_fault.items()):
        fault_correct = sum(row["assessment"] == "correct" for row in rows)
        per_fault.append({
            "fault_id": fault_id,
            "injected_faults": len(rows),
            "correctly_identified": fault_correct,
            "detection_accuracy_percent": round(100.0 * fault_correct / len(rows), 2),
            "assessment_counts": {
                status: sum(row["assessment"] == status for row in rows)
                for status in sorted(_ASSESSMENTS)
            },
        })

    return {
        "schema_version": 1,
        "metric": "correctly_identified_injected_faults / all_injected_faults",
        "summary": {
            "injected_faults": total,
            "correctly_identified_faults": correct,
            "detection_accuracy_percent": round(100.0 * correct / total, 2),
            "reviewed_cases": reviewed,
            "review_coverage_percent": round(100.0 * reviewed / total, 2),
            "assessment_counts": counts,
        },
        "per_fault": per_fault,
        "cases": normalized,
        "limitations": [
            "Scores are only as reliable as the injected-fault ground truth and reviewer assessment.",
            "Unreviewed cases remain in the denominator and are not counted as correctly identified.",
            "This evaluator computes metrics; it does not inject faults, test hardware, or verify diagnoses.",
            "Use repeat trials and controlled wiring conditions before generalizing results.",
        ],
    }


def load_fault_cases(path: Path) -> dict[str, Any]:
    """Read a bounded UTF-8 JSON input document."""
    if not path.is_file():
        raise FileNotFoundError("Fault-evaluation file not found: {}".format(path))
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("Fault-evaluation input exceeds the 5 MB safety limit.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read fault-evaluation JSON: {}".format(exc)) from exc
    if not isinstance(document, dict):
        raise ValueError("Fault-evaluation input must be a JSON object.")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score human-reviewed injected-fault diagnosis cases."
    )
    parser.add_argument("input_json", help="JSON file with injected fault cases and review assessments.")
    parser.add_argument(
        "--output",
        default="./results/fault_injection_evaluation.json",
        help="Path for the metric report JSON (default: ./results/fault_injection_evaluation.json).",
    )
    args = parser.parse_args(argv)
    try:
        result = evaluate_fault_cases(load_fault_cases(Path(args.input_json)))
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("Fault evaluation stopped: {}".format(exc), file=sys.stderr)
        return 2

    summary = result["summary"]
    print("Fault-injection evaluation complete")
    print("Injected faults: {}".format(summary["injected_faults"]))
    print("Correctly identified: {}".format(summary["correctly_identified_faults"]))
    print("Detection accuracy: {:.2f}%".format(summary["detection_accuracy_percent"]))
    print("Review coverage: {:.2f}%".format(summary["review_coverage_percent"]))
    print("Report: {}".format(output_path))
    print("This report scores supplied reviews; it does not independently confirm hardware results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
