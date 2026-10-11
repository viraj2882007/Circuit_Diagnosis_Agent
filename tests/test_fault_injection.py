import json

import pytest

from mcu_diagnostic_agent.fault_injection import evaluate_fault_cases, load_fault_cases


def test_accuracy_uses_all_injected_faults_and_reports_review_coverage():
    result = evaluate_fault_cases({
        "cases": [
            {"case_id": "gpio-1", "fault_id": "gpio_open", "injected_fault": "D2-D3 jumper removed", "assessment": "correct"},
            {"case_id": "gpio-2", "fault_id": "gpio_open", "injected_fault": "D2-D3 jumper removed", "assessment": "missed"},
            {"case_id": "i2c-1", "fault_id": "i2c_sda_open", "injected_fault": "SDA disconnected", "assessment": "incorrect"},
            {"case_id": "i2c-2", "fault_id": "i2c_scl_open", "injected_fault": "SCL disconnected"},
        ]
    })

    summary = result["summary"]
    assert summary["injected_faults"] == 4
    assert summary["correctly_identified_faults"] == 1
    assert summary["detection_accuracy_percent"] == 25.0
    assert summary["reviewed_cases"] == 3
    assert summary["review_coverage_percent"] == 75.0
    assert len(result["per_fault"]) == 3
    assert "does not inject faults" in " ".join(result["limitations"]).lower()


def test_fault_evaluator_rejects_duplicate_case_ids():
    with pytest.raises(ValueError, match="Duplicate case_id"):
        evaluate_fault_cases({"cases": [
            {"case_id": "same", "fault_id": "gpio_open", "injected_fault": "jumper removed"},
            {"case_id": "same", "fault_id": "i2c_open", "injected_fault": "SDA disconnected"},
        ]})


def test_fault_evaluator_rejects_unknown_assessment():
    with pytest.raises(ValueError, match="Invalid assessment"):
        evaluate_fault_cases({"cases": [
            {"case_id": "gpio-1", "fault_id": "gpio_open", "injected_fault": "jumper removed", "assessment": "probably"},
        ]})


def test_load_fault_cases_reads_utf8_json(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [
        {"case_id": "i2c-1", "fault_id": "i2c_sda_open", "injected_fault": "SDA disconnected"},
    ]}), encoding="utf-8")
    assert load_fault_cases(path)["cases"][0]["fault_id"] == "i2c_sda_open"
