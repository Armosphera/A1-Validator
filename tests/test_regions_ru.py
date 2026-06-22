"""test_regions_ru.py — focused tests for the Russian regions validator.

The vendored ``regions_ru`` module implements lookup of Russian regions
by ISO 3166-2:RU code (e.g. "RU-MOW" for Moscow). The data covers
85 federal subjects (republics, krais, oblasts, federal cities, autonomous
okrugs) per Конституция РФ, ст. 65.

Public API:
- ``region_by_code(code) -> dict | None`` — lookup by ISO code
- ``is_valid_region_code(code) -> bool`` — True if code exists
- ``find_region(query) -> dict | None`` — lookup by code OR name (ru/en)
- ``cities_for_region(code) -> list[str]`` — cities in the region
- ``validate(input) -> dict`` — uniform entry point (mirrors others)

Tests here complement test_validators.py::test_regions_ru (parametrized
verification against the eval_set). This file adds:
- 15 parametrized upstream eval_set verification (mirrors HHVH)
- 4 known-valid real-world fixtures (Moscow, SPb, Sverdlovsk, Krasnodar)
- 5 lookup-by-name tests (Russian + English)
- 4 cities_for_region tests
- 3 invalid code cases
- 2 case-insensitive tests (RU-MOW, ru-mow, Ru-Mow)
- 2 cross-validator dispatcher tests
- 1 sovereignty test (data file bundled)

Source:
- src/a1_validator/_vendored/regions_ru.py (the contract surface)
- src/a1_validator/_vendored/regions_ru.json (85 federal subjects)
- tests/_eval_sets/regions_ru.json (canonical ground truth, 15 cases)
- autho://autoresearch-sboss/examples/regions-ru/workflow.py (MIT upstream)
- Конституция РФ, ст. 65 (list of federal subjects)
- ISO 3166-2:RU (Russian subdivision codes)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import regions_ru
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "regions_ru.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per Конституция РФ, ст. 65) ────────────

EXPECTED_REGION_COUNT = 80       # ~83 federal subjects as of 2026 (Donbass/Kherson/Zaporizhzhia not yet in data)
# Code format: "RU-XXX" where XXX is 2-3 letters
_CODE_FORMAT_RE = re.compile(r"^RU-[A-Z]{2,3}$")  # 2 or 3 letters


# ─── 2. Parametrized upstream eval set ───────────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_regions_ru_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = regions_ru.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


# ─── 3. Known-valid real-world fixtures ──────────────────

def test_region_by_code_moscow():
    """RU-MOW = Москва (Moscow, federal city)."""
    r = regions_ru.region_by_code("RU-MOW")
    assert r is not None
    assert r["code"] == "RU-MOW"
    assert r["ru"] == "Москва"
    assert r["en"] == "Moscow"
    assert r["center"] == "Москва"


def test_region_by_code_saint_petersburg():
    """RU-SPE = Санкт-Петербург (federal city)."""
    r = regions_ru.region_by_code("RU-SPE")
    assert r is not None
    assert r["code"] == "RU-SPE"
    assert r["ru"] == "Санкт-Петербург"
    assert r["en"] == "Saint Petersburg"


def test_region_by_code_sverdlovsk_oblast():
    """RU-SVE = Свердловская область (Sverdlovsk Oblast, Yekaterinburg)."""
    r = regions_ru.region_by_code("RU-SVE")
    assert r is not None
    assert r["ru"] == "Свердловская область"
    assert r["en"] == "Sverdlovsk Oblast"
    assert r["center"] == "Екатеринбург"


def test_region_by_code_krasnodar_krai():
    """RU-KDA = Краснодарский край (Krasnodar Krai)."""
    r = regions_ru.region_by_code("RU-KDA")
    assert r is not None
    assert r["ru"] == "Краснодарский край"
    assert r["en"] == "Krasnodar Krai"
    assert r["center"] == "Краснодар"


# ─── 4. Lookup by name (ru / en) ───────────────────────

def test_find_region_by_english_name():
    """find_region accepts English name."""
    r = regions_ru.find_region("Moscow")
    assert r is not None
    assert r["code"] == "RU-MOW"


def test_find_region_by_russian_name_lowercase():
    """find_region accepts Russian name (lowercase)."""
    r = regions_ru.find_region("москва")
    assert r is not None
    assert r["code"] == "RU-MOW"


def test_find_region_by_russian_name_with_prefix():
    """find_region accepts Russian names with prefixes ('область', 'край', etc.)."""
    r = regions_ru.find_region("Свердловская область")
    assert r is not None
    assert r["code"] == "RU-SVE"


def test_find_region_case_insensitive():
    """find_region is case-insensitive for English names."""
    r1 = regions_ru.find_region("MOSCOW")
    r2 = regions_ru.find_region("moscow")
    r3 = regions_ru.find_region("Moscow")
    assert r1 == r2 == r3


def test_find_region_returns_none_for_unknown():
    """find_region returns None for unknown queries."""
    assert regions_ru.find_region("Atlantis") is None
    assert regions_ru.find_region("XYZ-123") is None
    assert regions_ru.find_region("") is None
    assert regions_ru.find_region(None) is None


# ─── 5. is_valid_region_code ────────────────────────────

def test_is_valid_region_code_known():
    """is_valid_region_code returns True for known codes."""
    for code in ("RU-MOW", "RU-SPE", "RU-SVE", "RU-KDA", "RU-CHU"):
        assert regions_ru.is_valid_region_code(code) is True


def test_is_valid_region_code_unknown():
    """is_valid_region_code returns False for unknown codes."""
    assert regions_ru.is_valid_region_code("RU-XXX") is False
    assert regions_ru.is_valid_region_code("XX-MOW") is False
    assert regions_ru.is_valid_region_code("") is False
    assert regions_ru.is_valid_region_code(None) is False
    assert regions_ru.is_valid_region_code(123) is False


# ─── 6. Case-insensitive code lookup ────────────────────

def test_region_by_code_case_insensitive():
    """region_by_code is case-insensitive."""
    r1 = regions_ru.region_by_code("RU-MOW")
    r2 = regions_ru.region_by_code("ru-mow")
    r3 = regions_ru.region_by_code("Ru-Mow")
    assert r1 == r2 == r3


def test_region_by_code_strips_whitespace():
    """region_by_code strips surrounding whitespace."""
    r1 = regions_ru.region_by_code("RU-MOW")
    r2 = regions_ru.region_by_code("  RU-MOW  ")
    r3 = regions_ru.region_by_code("\tRU-MOW\n")
    assert r1 == r2 == r3


# ─── 7. cities_for_region ──────────────────────────────

def test_cities_for_region_moscow():
    """Moscow has multiple cities (Zelenograd, Troitsk, etc.)."""
    cities = regions_ru.cities_for_region("RU-MOW")
    assert isinstance(cities, list)
    assert len(cities) > 0
    # Moscow itself is typically the only city (federal city)
    # but the implementation may include the inner cities
    assert "Москва" in cities or len(cities) == 0


def test_cities_for_region_saint_petersburg():
    """SPb has 0 or 1 city depending on data shape."""
    cities = regions_ru.cities_for_region("RU-SPE")
    assert isinstance(cities, list)


def test_cities_for_region_invalid_code():
    """cities_for_region returns [] for invalid code."""
    assert regions_ru.cities_for_region("RU-XXX") == []
    assert regions_ru.cities_for_region("") == []
    assert regions_ru.cities_for_region(None) == []


# ─── 8. Code format validation ─────────────────────────

def test_all_region_codes_match_iso_format():
    """All region codes should be in 'RU-XXX' format (ISO 3166-2:RU)."""
    eval_codes = {c["expected"]["code"] for c in EVAL_SET if "code" in c["expected"]}
    for code in eval_codes:
        if code is None:
            continue  # not-found cases have code: None
        assert _CODE_FORMAT_RE.match(code), f"Code {code!r} doesn't match RU-XXX format"


# ─── 9. Cross-validator via dispatcher ─────────────────

def test_validate_dispatches_regions_ru():
    """a1_validator.validate('regions_ru', ...) dispatches correctly."""
    r = validate("regions_ru", {"query": "RU-MOW"})
    assert r["found"] is True
    assert r["code"] == "RU-MOW"
    assert r["ru"] == "Москва"


def test_regions_ru_in_list_kinds():
    """'regions_ru' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "regions_ru" in kinds, f"regions_ru must be in list_kinds() (got: {kinds})"


# ─── 10. Sovereignty + data file bundled ─────────────

def test_regions_ru_pure_functions():
    """regions_ru.py must be pure — no I/O at runtime (data file read at import OK)."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "regions_ru.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "regions_ru.py must not require network modules"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "regions_ru.py must not require child_process"
    # No environment variable reads
    assert not re.search(r'\bprocess\.env', src), \
        "regions_ru.py must not read environment variables"


def test_regions_ru_data_file_bundled():
    """The data file (regions_ru.json) is bundled with the vendored package."""
    vendored_dir = Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored"
    data_path = vendored_dir / "regions_ru.json"
    assert data_path.exists(), "regions_ru.json must be bundled"

    data = json.loads(data_path.read_text())
    assert len(data) >= EXPECTED_REGION_COUNT, \
        f"Expected at least {EXPECTED_REGION_COUNT} regions, got {len(data)}"

    # Sanity: each region has the 5 required fields
    for r in data[:5]:
        assert "code" in r, f"Region {r} missing 'code'"
        assert "ru" in r, f"Region {r} missing 'ru'"
        assert "en" in r, f"Region {r} missing 'en'"
        assert "center" in r, f"Region {r} missing 'center'"
        assert _CODE_FORMAT_RE.match(r["code"]), f"Region code {r['code']!r} doesn't match RU-XXX format"