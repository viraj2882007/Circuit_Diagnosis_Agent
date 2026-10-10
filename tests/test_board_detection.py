from types import SimpleNamespace

from mcu_diagnostic_agent.board_detection import detect_connected_boards
from mcu_diagnostic_agent.board_profiles import (
    build_diagnostic_plan,
    find_profiles_by_usb_id,
    get_board_profile,
)


def fake_port(device="COM9", description="Arduino Uno (COM9)", vid=0x2341, pid=0x0043):
    return SimpleNamespace(
        device=device,
        description=description,
        hwid="USB VID:PID={:04X}:{:04X}".format(vid, pid) if vid is not None and pid is not None else "n/a",
        vid=vid,
        pid=pid,
        product=description,
        manufacturer="Arduino",
        serial_number="TEST",
    )


def test_detects_uno_r3_from_exact_usb_identity():
    result = detect_connected_boards([fake_port()])

    assert len(result) == 1
    assert result[0].recognized is True
    assert result[0].profile_id == "arduino_uno_r3"
    assert result[0].profile.mcu_part == "ATmega328P"
    assert result[0].confidence == "high"
    assert result[0].match_method == "exact_usb_vid_pid"
    assert result[0].to_dict()["vid_pid"] == "2341:0043"


def test_description_only_match_is_a_candidate_not_an_auto_detection():
    result = detect_connected_boards([
        fake_port(description="Arduino Uno compatible board", vid=0x1A86, pid=0x7523)
    ])

    assert result[0].recognized is False
    assert result[0].profile_id is None
    assert result[0].candidate_profile_id == "arduino_uno_r3"
    assert result[0].confidence == "low"


def test_unknown_usb_bridge_is_not_misidentified_from_generic_description():
    result = detect_connected_boards([
        fake_port(description="USB-SERIAL CH340", vid=0x1A86, pid=0x7523)
    ])

    assert result[0].recognized is False
    assert result[0].candidate_profile_id is None
    assert result[0].match_method == "unrecognized"


def test_uno_profile_maps_pins_and_no_native_dac():
    profile = get_board_profile("ARDUINO_UNO_R3")

    assert profile is not None
    assert profile.analog_inputs == ("A0", "A1", "A2", "A3", "A4", "A5")
    assert profile.pwm_pins == ("D3", "D5", "D6", "D9", "D10", "D11")
    assert profile.i2c_pins == (("SDA", "A4"), ("SCL", "A5"))
    assert profile.dac_outputs == ()
    assert find_profiles_by_usb_id(0x2341, 0x0043)[0].board_id == "arduino_uno_r3"


def test_default_plan_is_preview_only_and_excludes_memory_writes():
    profile = get_board_profile("arduino_uno_r3")
    assert profile is not None

    plan = build_diagnostic_plan(profile)
    tests = {test["id"]: test for test in plan["tests"]}

    assert plan["plan_only"] is True
    assert plan["execution_started"] is False
    assert plan["adapter"]["implementation_available"] is True
    assert tests["gpio_loopback"]["status"] == "requires_wiring"
    assert tests["pwm_output_check"]["pins"] == ["D3", "D5", "D6", "D9", "D10", "D11"]
    assert tests["memory_write_tests"]["status"] == "excluded_by_default"
    assert "eeprom_write_read" not in tests
    assert plan["not_supported"]["dac_outputs"] == []


def test_destructive_tests_are_only_listed_after_explicit_plan_opt_in():
    profile = get_board_profile("arduino_uno_r3")
    assert profile is not None

    plan = build_diagnostic_plan(profile, include_destructive=True)
    tests = {test["id"]: test for test in plan["tests"]}

    assert tests["eeprom_write_read"]["status"] == "explicit_approval_required"
    assert tests["flash_integrity"]["status"] == "blocked_without_recovery_strategy"


def test_no_ports_returns_an_empty_detection_list():
    assert detect_connected_boards([]) == []



def test_profile_without_execution_adapter_is_not_claimed_as_runnable():
    profile = get_board_profile("arduino_mega_2560_r3")
    assert profile is not None

    plan = build_diagnostic_plan(profile)

    assert plan["adapter"]["implementation_available"] is False
    assert plan["adapter"]["mode"] == "profile_and_plan_preview_only"
