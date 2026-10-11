from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_zephyr_ram_tests_do_not_write_to_a_hard_coded_address():
    files = [
        REPO_ROOT / "zephyr_app" / "src" / "tests" / "basic_tests.c",
        REPO_ROOT / "zephyr_app" / "src" / "tests" / "memory_tests.c",
    ]
    for path in files:
        source = path.read_text(encoding="utf-8")
        assert "(volatile uint32_t *)0x20000000" not in source


def test_generic_zephyr_flash_write_and_erase_checks_are_non_destructive():
    source = (REPO_ROOT / "zephyr_app" / "src" / "tests" / "memory_tests.c").read_text(encoding="utf-8")
    assert "Flash write/read test disabled" in source
    assert "Flash erase test disabled" in source
    assert "flash_erase(FLASH_DEV" not in source
    assert "flash_write(FLASH_DEV" not in source


def test_zephyr_suite_registry_uses_real_test_case_arrays():
    source = (REPO_ROOT / "zephyr_app" / "src" / "main.c").read_text(encoding="utf-8")
    assert "extern const struct test_case adc_tests[];" in source
    assert "extern const struct test_case i2c_tests[];" in source
    assert '{"adc", adc_tests, false}' in source
    assert '{"i2c", i2c_tests, false}' in source
    assert "count_test_cases(entry->cases)" in source
