from mcu_diagnostic_agent.avrdude_support import locate_avrdude, parse_device_signature


def test_parse_device_signature_normalizes_hex_bytes():
    assert parse_device_signature("Device signature = 1e 95 0f (ATmega328P)") == "1E 95 0F"
    assert parse_device_signature("Device signature = AB CD EF") == "AB CD EF"


def test_parse_device_signature_returns_none_when_missing():
    assert parse_device_signature("programmer is not responding") is None


def test_locate_avrdude_accepts_explicit_paths(tmp_path):
    executable = tmp_path / "avrdude.exe"
    config = tmp_path / "avrdude.conf"
    executable.write_text("placeholder", encoding="utf-8")
    config.write_text("placeholder", encoding="utf-8")

    binary, config_path, message = locate_avrdude(executable, config)

    assert binary == executable
    assert config_path == config
    assert message == ""


def test_locate_avrdude_reports_missing_explicit_paths(tmp_path):
    executable = tmp_path / "missing-avrdude.exe"

    binary, config, message = locate_avrdude(executable)

    assert binary is None
    assert config is None
    assert "does not exist" in message
