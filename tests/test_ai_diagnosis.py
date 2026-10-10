import io
import json
import urllib.request

import pytest

from mcu_diagnostic_agent.ai_diagnosis import generate_ai_analysis


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        generate_ai_analysis({"mcu_family": "stm32"}, api_key=None)


def test_analysis_uses_nvidia_nim_and_expected_model(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "## Executive summary\nEvidence is limited."}}]
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = generate_ai_analysis(
        {
            "mcu_family": "stm32",
            "mcu_part": "STM32F407VG",
            "suites": [],
            "external_peripherals": [],
        },
        api_key="test-token",
    )
    assert captured["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert captured["payload"]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert result.startswith("## Executive summary")



def test_all_pass_report_returns_deterministic_no_fault_summary_without_calling_nim(monkeypatch):
    def unexpected_network_call(*args, **kwargs):
        raise AssertionError("All-pass summary should not call the generative API")

    monkeypatch.setattr(urllib.request, "urlopen", unexpected_network_call)
    report = {
        "mcu_family": "arduino",
        "mcu_part": "Arduino Uno R3 (ATmega328P)",
        "passed": 2,
        "failed": 0,
        "skipped": 1,
        "suites": [
            {
                "name": "Host Interface",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "tests": [
                    {"name": "USB serial", "status": "pass", "details": "COM9 responsive"},
                ],
            },
            {
                "name": "GPIO",
                "passed": 1,
                "failed": 0,
                "skipped": 1,
                "tests": [
                    {"name": "D2-D3 loopback", "status": "pass", "details": "LOW/HIGH observed"},
                    {"name": "ADC A0", "status": "skip", "details": "Not wired"},
                ],
            },
        ],
        "external_peripherals": [
            {"name": "I2C sensor", "status": "unknown", "observed": "Not scanned"}
        ],
        "untested_peripherals": ["ADC A0-A5", "PWM frequency not measured"],
    }

    result = generate_ai_analysis(report, api_key=None)

    assert result.startswith("[DETERMINISTIC_ALL_PASS_SUMMARY]")
    assert "No fault was found in the tests performed" in result
    assert "Repair or replacement is not indicated" in result
    assert "ADC A0" in result
    assert "I2C sensor" in result
    assert "battery packs" not in result.lower()
    assert "Repair steps" not in result
