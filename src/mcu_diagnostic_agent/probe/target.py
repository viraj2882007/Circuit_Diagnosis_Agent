"""
Target MCU definitions and database.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class MCUArchitecture(Enum):
    """MCU architecture types."""
    CORTEX_M0 = "cortex-m0"
    CORTEX_M0PLUS = "cortex-m0+"
    CORTEX_M3 = "cortex-m3"
    CORTEX_M4 = "cortex-m4"
    CORTEX_M7 = "cortex-m7"
    CORTEX_M23 = "cortex-m23"
    CORTEX_M33 = "cortex-m33"
    ESP32 = "esp32"
    RISCV = "riscv"
    AVR = "avr"


class ProbeInterface(Enum):
    """Debug probe interfaces."""
    SWD = "swd"
    JTAG = "jtag"
    UART = "uart"


@dataclass
class MemoryRegion:
    """Memory region definition."""
    name: str
    start: int
    size: int
    is_flash: bool = False
    is_ram: bool = False
    permissions: str = "rw"


@dataclass
class PeripheralInfo:
    """Peripheral availability."""
    gpio_ports: List[str] = field(default_factory=list)
    adc_channels: int = 0
    dac_channels: int = 0
    uart_count: int = 0
    spi_count: int = 0
    i2c_count: int = 0
    timer_count: int = 0
    pwm_channels: int = 0
    usb: bool = False
    can: bool = False
    ethernet: bool = False
    wifi: bool = False
    bluetooth: bool = False


@dataclass
class FlashAlgorithm:
    """Flash programming algorithm."""
    name: str
    family: str
    start_address: int
    page_size: int
    sector_size: int
    flash_size: int
    ram_start: int
    ram_size: int


@dataclass
class TargetMCU:
    """Complete target MCU definition."""
    family: str
    part_number: str
    architecture: MCUArchitecture
    flash_size_kb: int
    ram_size_kb: int
    cpu_freq_mhz: int
    supported_interfaces: List[ProbeInterface]
    default_interface: ProbeInterface
    memory_map: List[MemoryRegion] = field(default_factory=list)
    flash_algorithms: List[FlashAlgorithm] = field(default_factory=list)
    peripherals: PeripheralInfo = field(default_factory=PeripheralInfo)
    zephyr_board: str = ""
    aliases: List[str] = field(default_factory=list)


# STM32 Family Targets
STM32_TARGETS = {
    # STM32F0
    "STM32F030R8": TargetMCU(
        family="stm32",
        part_number="STM32F030R8",
        architecture=MCUArchitecture.CORTEX_M0,
        flash_size_kb=64,
        ram_size_kb=8,
        cpu_freq_mhz=48,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 64*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 8*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f0x", "STM32F0", 0x08000000, 1024, 1024, 64*1024, 0x20000000, 8*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "F"],
            adc_channels=16,
            uart_count=4,
            spi_count=2,
            i2c_count=2,
            timer_count=11,
        ),
        zephyr_board="nucleo_f030r8",
        aliases=["STM32F030"],
    ),

    # STM32F1
    "STM32F103C8": TargetMCU(
        family="stm32",
        part_number="STM32F103C8",
        architecture=MCUArchitecture.CORTEX_M3,
        flash_size_kb=64,
        ram_size_kb=20,
        cpu_freq_mhz=72,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 64*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 20*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f1x", "STM32F1", 0x08000000, 1024, 1024, 64*1024, 0x20000000, 20*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D"],
            adc_channels=18,
            uart_count=3,
            spi_count=2,
            i2c_count=2,
            timer_count=11,
            can=True,
        ),
        zephyr_board="nucleo_f103rb",
        aliases=["STM32F103", "BluePill"],
    ),

    "STM32F103RB": TargetMCU(
        family="stm32",
        part_number="STM32F103RB",
        architecture=MCUArchitecture.CORTEX_M3,
        flash_size_kb=128,
        ram_size_kb=20,
        cpu_freq_mhz=72,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 128*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 20*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f1x", "STM32F1", 0x08000000, 1024, 1024, 128*1024, 0x20000000, 20*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E"],
            adc_channels=18,
            uart_count=5,
            spi_count=3,
            i2c_count=2,
            timer_count=11,
            can=True,
        ),
        zephyr_board="nucleo_f103rb",
        aliases=["STM32F103"],
    ),

    # STM32F3
    "STM32F303RE": TargetMCU(
        family="stm32",
        part_number="STM32F303RE",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=512,
        ram_size_kb=80,
        cpu_freq_mhz=72,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 512*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 80*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f3x", "STM32F3", 0x08000000, 2048, 2048, 512*1024, 0x20000000, 80*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "F"],
            adc_channels=18,
            dac_channels=2,
            uart_count=5,
            spi_count=3,
            i2c_count=3,
            timer_count=13,
            can=True,
        ),
        zephyr_board="nucleo_f303re",
        aliases=["STM32F303"],
    ),

    # STM32F4
    "STM32F401RE": TargetMCU(
        family="stm32",
        part_number="STM32F401RE",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=512,
        ram_size_kb=96,
        cpu_freq_mhz=84,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 512*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 96*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f4x", "STM32F4", 0x08000000, 16384, 16384, 512*1024, 0x20000000, 96*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "H"],
            adc_channels=16,
            uart_count=4,
            spi_count=3,
            i2c_count=3,
            timer_count=14,
        ),
        zephyr_board="nucleo_f401re",
        aliases=["STM32F401"],
    ),

    "STM32F407VG": TargetMCU(
        family="stm32",
        part_number="STM32F407VG",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=1024,
        ram_size_kb=192,
        cpu_freq_mhz=168,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 1024*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 192*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f4x", "STM32F4", 0x08000000, 16384, 16384, 1024*1024, 0x20000000, 192*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            adc_channels=18,
            dac_channels=2,
            uart_count=6,
            spi_count=6,
            i2c_count=3,
            timer_count=14,
            can=True,
            ethernet=True,
        ),
        zephyr_board="nucleo_f407zg",
        aliases=["STM32F407", "STM32F4Discovery"],
    ),

    "STM32F411CE": TargetMCU(
        family="stm32",
        part_number="STM32F411CE",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=512,
        ram_size_kb=128,
        cpu_freq_mhz=100,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 512*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 128*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32f4x", "STM32F4", 0x08000000, 16384, 16384, 512*1024, 0x20000000, 128*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D"],
            adc_channels=16,
            uart_count=4,
            spi_count=5,
            i2c_count=3,
            timer_count=14,
        ),
        zephyr_board="nucleo_f411re",
        aliases=["STM32F411"],
    ),

    # STM32G4
    "STM32G431KB": TargetMCU(
        family="stm32",
        part_number="STM32G431KB",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=128,
        ram_size_kb=32,
        cpu_freq_mhz=170,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 128*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 32*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32g4x", "STM32G4", 0x08000000, 2048, 2048, 128*1024, 0x20000000, 32*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C"],
            adc_channels=18,
            dac_channels=2,
            uart_count=5,
            spi_count=3,
            i2c_count=3,
            timer_count=14,
            can=True,
            usb=True,
        ),
        zephyr_board="nucleo_g431rb",
        aliases=["STM32G431"],
    ),

    # STM32H7
    "STM32H743ZI": TargetMCU(
        family="stm32",
        part_number="STM32H743ZI",
        architecture=MCUArchitecture.CORTEX_M7,
        flash_size_kb=2048,
        ram_size_kb=1024,
        cpu_freq_mhz=480,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 2048*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 1024*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32h7x", "STM32H7", 0x08000000, 131072, 131072, 2048*1024, 0x20000000, 1024*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"],
            adc_channels=20,
            dac_channels=2,
            uart_count=8,
            spi_count=6,
            i2c_count=4,
            timer_count=22,
            can=True,
            ethernet=True,
            usb=True,
        ),
        zephyr_board="nucleo_h743zi",
        aliases=["STM32H743"],
    ),

    # STM32L4
    "STM32L432KC": TargetMCU(
        family="stm32",
        part_number="STM32L432KC",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=256,
        ram_size_kb=64,
        cpu_freq_mhz=80,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 256*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 64*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32l4x", "STM32L4", 0x08000000, 2048, 2048, 256*1024, 0x20000000, 64*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "H"],
            adc_channels=16,
            dac_channels=2,
            uart_count=3,
            spi_count=3,
            i2c_count=3,
            timer_count=11,
            usb=True,
        ),
        zephyr_board="nucleo_l432kc",
        aliases=["STM32L432"],
    ),

    "STM32L476RG": TargetMCU(
        family="stm32",
        part_number="STM32L476RG",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=1024,
        ram_size_kb=128,
        cpu_freq_mhz=80,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.JTAG],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x08000000, 1024*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 128*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("stm32l4x", "STM32L4", 0x08000000, 2048, 2048, 1024*1024, 0x20000000, 128*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "F", "G", "H"],
            adc_channels=16,
            dac_channels=2,
            uart_count=5,
            spi_count=3,
            i2c_count=3,
            timer_count=13,
            usb=True,
            can=True,
        ),
        zephyr_board="nucleo_l476rg",
        aliases=["STM32L476"],
    ),
}

# ESP32 Family Targets
ESP32_TARGETS = {
    "ESP32": TargetMCU(
        family="esp32",
        part_number="ESP32",
        architecture=MCUArchitecture.ESP32,
        flash_size_kb=4096,  # External flash
        ram_size_kb=520,
        cpu_freq_mhz=240,
        supported_interfaces=[ProbeInterface.JTAG, ProbeInterface.UART],
        default_interface=ProbeInterface.JTAG,
        memory_map=[
            MemoryRegion("Flash", 0x40000000, 4096*1024, is_flash=True),
            MemoryRegion("RAM", 0x3FC88000, 520*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("esp32", "ESP32", 0x40000000, 4096, 4096, 4096*1024, 0x3FC88000, 520*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["0-39"],
            adc_channels=18,
            dac_channels=2,
            uart_count=3,
            spi_count=4,
            i2c_count=2,
            timer_count=4,
            pwm_channels=16,
            usb=True,
            can=True,
            wifi=True,
            bluetooth=True,
        ),
        zephyr_board="esp32_devkitc",
        aliases=["ESP32-D0WDQ6", "ESP32-D0WD"],
    ),

    "ESP32S2": TargetMCU(
        family="esp32",
        part_number="ESP32S2",
        architecture=MCUArchitecture.ESP32,
        flash_size_kb=4096,
        ram_size_kb=320,
        cpu_freq_mhz=240,
        supported_interfaces=[ProbeInterface.JTAG, ProbeInterface.UART],
        default_interface=ProbeInterface.JTAG,
        memory_map=[
            MemoryRegion("Flash", 0x40000000, 4096*1024, is_flash=True),
            MemoryRegion("RAM", 0x3FC88000, 320*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("esp32s2", "ESP32S2", 0x40000000, 4096, 4096, 4096*1024, 0x3FC88000, 320*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["0-45"],
            adc_channels=20,
            uart_count=2,
            spi_count=4,
            i2c_count=2,
            timer_count=4,
            usb=True,
            wifi=True,
        ),
        zephyr_board="esp32s2_devkitc",
        aliases=["ESP32-S2"],
    ),

    "ESP32S3": TargetMCU(
        family="esp32",
        part_number="ESP32S3",
        architecture=MCUArchitecture.ESP32,
        flash_size_kb=4096,
        ram_size_kb=512,
        cpu_freq_mhz=240,
        supported_interfaces=[ProbeInterface.JTAG, ProbeInterface.UART],
        default_interface=ProbeInterface.JTAG,
        memory_map=[
            MemoryRegion("Flash", 0x40000000, 4096*1024, is_flash=True),
            MemoryRegion("RAM", 0x3FC88000, 512*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("esp32s3", "ESP32S3", 0x40000000, 4096, 4096, 4096*1024, 0x3FC88000, 512*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["0-47"],
            adc_channels=20,
            uart_count=3,
            spi_count=4,
            i2c_count=2,
            timer_count=4,
            usb=True,
            wifi=True,
            bluetooth=True,
        ),
        zephyr_board="esp32s3_devkitc",
        aliases=["ESP32-S3"],
    ),

    "ESP32C3": TargetMCU(
        family="esp32",
        part_number="ESP32C3",
        architecture=MCUArchitecture.RISCV,
        flash_size_kb=4096,
        ram_size_kb=400,
        cpu_freq_mhz=160,
        supported_interfaces=[ProbeInterface.JTAG, ProbeInterface.UART],
        default_interface=ProbeInterface.JTAG,
        memory_map=[
            MemoryRegion("Flash", 0x40000000, 4096*1024, is_flash=True),
            MemoryRegion("RAM", 0x3FC88000, 400*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("esp32c3", "ESP32C3", 0x40000000, 4096, 4096, 4096*1024, 0x3FC88000, 400*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["0-22"],
            adc_channels=6,
            uart_count=2,
            spi_count=2,
            i2c_count=1,
            timer_count=2,
            usb=True,
            wifi=True,
            bluetooth=True,
        ),
        zephyr_board="esp32c3_devkitc",
        aliases=["ESP32-C3"],
    ),
}

# RP2040 Targets
RP2040_TARGETS = {
    "RP2040": TargetMCU(
        family="rp2040",
        part_number="RP2040",
        architecture=MCUArchitecture.CORTEX_M0PLUS,
        flash_size_kb=2048,  # External flash (typically 2MB)
        ram_size_kb=264,
        cpu_freq_mhz=133,
        supported_interfaces=[ProbeInterface.SWD],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x10000000, 2048*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 264*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("rp2040", "RP2040", 0x10000000, 256, 4096, 2048*1024, 0x20000000, 264*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["0-29"],
            adc_channels=4,
            uart_count=2,
            spi_count=2,
            i2c_count=2,
            timer_count=4,
            pwm_channels=16,
            usb=True,
        ),
        zephyr_board="rpi_pico",
        aliases=["RP2040", "Pico", "RP2040-Pico"],
    ),
}

# Arduino/AVR/SAMD Targets
ARDUINO_TARGETS = {
    "ATMEGA328P": TargetMCU(
        family="arduino",
        part_number="ATMEGA328P",
        architecture=MCUArchitecture.AVR,
        flash_size_kb=32,
        ram_size_kb=2,
        cpu_freq_mhz=16,
        supported_interfaces=[ProbeInterface.UART, ProbeInterface.SWD],
        default_interface=ProbeInterface.UART,
        memory_map=[
            MemoryRegion("Flash", 0x0000, 32*1024, is_flash=True),
            MemoryRegion("RAM", 0x0100, 2*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("avr109", "AVR", 0x0000, 128, 128, 32*1024, 0x0100, 2*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["B", "C", "D"],
            adc_channels=6,
            uart_count=1,
            spi_count=1,
            i2c_count=1,
            timer_count=3,
            pwm_channels=6,
        ),
        zephyr_board="arduino_uno",
        aliases=["Uno", "Nano", "ATMEGA328"],
    ),

    "ATMEGA2560": TargetMCU(
        family="arduino",
        part_number="ATMEGA2560",
        architecture=MCUArchitecture.AVR,
        flash_size_kb=256,
        ram_size_kb=8,
        cpu_freq_mhz=16,
        supported_interfaces=[ProbeInterface.UART, ProbeInterface.SWD],
        default_interface=ProbeInterface.UART,
        memory_map=[
            MemoryRegion("Flash", 0x0000, 256*1024, is_flash=True),
            MemoryRegion("RAM", 0x0100, 8*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("avr109", "AVR", 0x0000, 128, 128, 256*1024, 0x0100, 8*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L"],
            adc_channels=16,
            uart_count=4,
            spi_count=1,
            i2c_count=1,
            timer_count=6,
            pwm_channels=15,
        ),
        zephyr_board="arduino_mega",
        aliases=["Mega", "ATMEGA2560"],
    ),

    "ATSAMD21G18": TargetMCU(
        family="arduino",
        part_number="ATSAMD21G18",
        architecture=MCUArchitecture.CORTEX_M0PLUS,
        flash_size_kb=256,
        ram_size_kb=32,
        cpu_freq_mhz=48,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.UART],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x00000000, 256*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 32*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("samd21", "SAMD21", 0x00000000, 256, 256, 256*1024, 0x20000000, 32*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B"],
            adc_channels=14,
            dac_channels=1,
            uart_count=6,
            spi_count=6,
            i2c_count=6,
            timer_count=5,
            usb=True,
        ),
        zephyr_board="arduino_zero",
        aliases=["Zero", "SAMD21", "SAMD21G18"],
    ),

    "ATSAMD51J19": TargetMCU(
        family="arduino",
        part_number="ATSAMD51J19",
        architecture=MCUArchitecture.CORTEX_M4,
        flash_size_kb=512,
        ram_size_kb=192,
        cpu_freq_mhz=120,
        supported_interfaces=[ProbeInterface.SWD, ProbeInterface.UART],
        default_interface=ProbeInterface.SWD,
        memory_map=[
            MemoryRegion("Flash", 0x00000000, 512*1024, is_flash=True),
            MemoryRegion("RAM", 0x20000000, 192*1024, is_ram=True),
        ],
        flash_algorithms=[
            FlashAlgorithm("samd51", "SAMD51", 0x00000000, 512, 512, 512*1024, 0x20000000, 192*1024),
        ],
        peripherals=PeripheralInfo(
            gpio_ports=["A", "B", "C", "D"],
            adc_channels=16,
            dac_channels=2,
            uart_count=8,
            spi_count=6,
            i2c_count=6,
            timer_count=8,
            usb=True,
        ),
        zephyr_board="arduino_nano_33_iot",
        aliases=["Nano33IoT", "SAMD51"],
    ),
}

# Combined target database
ALL_TARGETS = {}
ALL_TARGETS.update(STM32_TARGETS)
ALL_TARGETS.update(ESP32_TARGETS)
ALL_TARGETS.update(RP2040_TARGETS)
ALL_TARGETS.update(ARDUINO_TARGETS)


def get_target(part_number: str) -> Optional[TargetMCU]:
    """Get target MCU by part number (case-insensitive)."""
    return ALL_TARGETS.get(part_number.upper())


def get_targets_by_family(family: str) -> List[TargetMCU]:
    """Get all targets for a family."""
    return [t for t in ALL_TARGETS.values() if t.family == family.lower()]


def find_target_by_alias(alias: str) -> Optional[TargetMCU]:
    """Find target by alias."""
    for target in ALL_TARGETS.values():
        if alias.upper() in [a.upper() for a in target.aliases]:
            return target
    return None