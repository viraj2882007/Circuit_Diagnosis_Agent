"""Small registry of common I2C devices with documented one-byte identity registers.

An address ACK is discovery evidence only. The host probes these ID registers only
when the user explicitly enables known-device identification.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class I2CIdentityProfile:
    """Minimal identity probe for a known I2C peripheral."""

    profile_id: str
    display_name: str
    addresses: Tuple[int, ...]
    identity_register: int
    expected_values: Tuple[int, ...]
    notes: str


I2C_IDENTITY_PROFILES: Tuple[I2CIdentityProfile, ...] = (
    I2CIdentityProfile(
        profile_id="bmp280",
        display_name="Bosch BMP280 pressure sensor",
        addresses=(0x76, 0x77),
        identity_register=0xD0,
        expected_values=(0x58,),
        notes="Chip ID register 0xD0; accepted values cover documented BMP280 revisions.",
    ),
    I2CIdentityProfile(
        profile_id="bmp180",
        display_name="Bosch BMP180 pressure sensor",
        addresses=(0x77,),
        identity_register=0xD0,
        expected_values=(0x55,),
        notes="Chip ID register 0xD0 is fixed to 0x55 in the BMP180 datasheet.",
    ),
    I2CIdentityProfile(
        profile_id="bme280",
        display_name="Bosch BME280 humidity/pressure/temperature sensor",
        addresses=(0x76, 0x77),
        identity_register=0xD0,
        expected_values=(0x60,),
        notes="Chip ID register 0xD0.",
    ),
    I2CIdentityProfile(
        profile_id="mpu6050",
        display_name="InvenSense MPU-6050 IMU",
        addresses=(0x68, 0x69),
        identity_register=0x75,
        expected_values=(0x68,),
        notes="WHO_AM_I register 0x75.",
    ),
    I2CIdentityProfile(
        profile_id="lis3dh",
        display_name="ST LIS3DH accelerometer",
        addresses=(0x18, 0x19),
        identity_register=0x0F,
        expected_values=(0x33,),
        notes="WHO_AM_I register 0x0F.",
    ),
    I2CIdentityProfile(
        profile_id="lsm6ds3",
        display_name="ST LSM6DS3 IMU",
        addresses=(0x6A, 0x6B),
        identity_register=0x0F,
        expected_values=(0x69,),
        notes="WHO_AM_I register 0x0F.",
    ),
)


def profiles_for_i2c_address(address: int) -> List[I2CIdentityProfile]:
    """Return known identity profiles that use this address."""
    return [profile for profile in I2C_IDENTITY_PROFILES if address in profile.addresses]


def match_i2c_identity(
    address: int,
    register: int,
    value: Optional[int],
) -> Optional[I2CIdentityProfile]:
    """Return a profile only when both address and ID-register value match."""
    if value is None:
        return None
    for profile in profiles_for_i2c_address(address):
        if profile.identity_register == register and value in profile.expected_values:
            return profile
    return None
