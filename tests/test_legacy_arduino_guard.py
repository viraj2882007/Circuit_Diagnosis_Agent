import asyncio
import io
from contextlib import redirect_stderr
from types import SimpleNamespace

from mcu_diagnostic_agent.orchestrator.agent import main_async


def test_generic_arduino_path_is_blocked_before_probe_or_firmware_access():
    stderr = io.StringIO()

    with redirect_stderr(stderr):
        exit_code = asyncio.run(main_async(SimpleNamespace(family="arduino")))

    assert exit_code == 2
    message = stderr.getvalue()
    assert "Safety stop" in message
    assert "mcu-uno-test --port COMx" in message
    assert "generic Arduino probe/flashing path is disabled" in message
