import json

import pytest

from mcu_diagnostic_agent.peripheral_observations import load_external_observations


def test_loads_and_normalizes_external_observations(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({
        "board": "test",
        "peripherals": [{
            "name": "OLED",
            "interface": "I2C",
            "status": "fail",
            "expected": "ACK at 0x3C",
            "observed": "NACK",
            "evidence": ["scan repeated twice"],
            "measurements": {"vcc_v": 3.3},
        }],
    }), encoding="utf-8")

    entries = load_external_observations(path)
    assert len(entries) == 1
    assert entries[0]["name"] == "OLED"
    assert entries[0]["status"] == "fail"
    assert entries[0]["measurements"]["vcc_v"] == 3.3


def test_rejects_unsupported_status(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({
        "peripherals": [{"name": "sensor", "status": "dead"}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid status"):
        load_external_observations(path)
