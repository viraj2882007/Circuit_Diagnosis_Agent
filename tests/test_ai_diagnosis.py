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
