from mcu_diagnostic_agent.external_devices import (
    match_i2c_identity,
    profiles_for_i2c_address,
)


def test_bme280_chip_id_is_identified_from_address_and_register_value():
    profile = match_i2c_identity(0x76, 0xD0, 0x60)

    assert profile is not None
    assert profile.profile_id == "bme280"


def test_bmp280_chip_id_is_identified_from_address_and_register_value():
    profile = match_i2c_identity(0x77, 0xD0, 0x58)

    assert profile is not None
    assert profile.profile_id == "bmp280"
    assert match_i2c_identity(0x77, 0xD0, 0x56) is None


def test_address_ack_without_expected_identity_does_not_identify_device():
    assert match_i2c_identity(0x76, 0xD0, 0x00) is None
    assert match_i2c_identity(0x3C, 0xD0, 0x60) is None


def test_mpu6050_profile_uses_who_am_i_register():
    candidates = profiles_for_i2c_address(0x68)

    assert [profile.profile_id for profile in candidates] == ["mpu6050"]
    assert match_i2c_identity(0x68, 0x75, 0x68).profile_id == "mpu6050"


def test_addresses_shared_by_sensor_profiles_are_not_enough_to_identify():
    candidates = profiles_for_i2c_address(0x76)

    assert {profile.profile_id for profile in candidates} == {"bmp280", "bme280"}
    assert match_i2c_identity(0x76, 0xD0, 0x60).profile_id == "bme280"
    assert match_i2c_identity(0x76, 0xD0, 0x58).profile_id == "bmp280"


def test_bmp180_chip_id_is_identified_from_address_and_register_value():
    profile = match_i2c_identity(0x77, 0xD0, 0x55)

    assert profile is not None
    assert profile.profile_id == "bmp180"
    assert match_i2c_identity(0x77, 0xD0, 0x58).profile_id == "bmp280"
    assert match_i2c_identity(0x76, 0xD0, 0x55) is None
