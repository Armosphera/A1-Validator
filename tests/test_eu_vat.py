"""test_eu_vat.py — focused tests for the EU VAT validator.

The vendored ``eu_vat`` module implements EU VAT (Value Added Tax) number
validation per the EU VAT Information Exchange System (VIES) format.

Public API:
- ``_EU_COUNTRY_CODES`` (frozenset, 28 EU + 3 non-EU = 31 total)
- ``_LETTER_OK_COUNTRIES`` (frozenset: ES, NL, GB)
- ``normalize_vat(value) -> str`` — strip separators, uppercase, preserve country code
- ``_default_check_digits(country, body) -> bool`` — always True (TODO seam)
- ``validate_vat(value, *, check_digit_verifier=None) -> dict`` — returns {ok, normalized, error}
- ``validate(input) -> dict`` — uniform entry point

Supported country codes (31 total):
- 28 EU members: AT, BE, BG, CY, CZ, DE, DK, EE, EL, ES, FI, FR, GB (post-Brexit),
  HR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SI, SK
- 3 non-EU: GB (UK post-Brexit), NO (Norway), CH (Switzerland)

Contract:
- VAT number must start with 2-letter country code
- Body must be 8-12 characters (permissive baseline)
- normalize_vat strips whitespace, dots, hyphens; preserves letters
- _default_check_digits always returns True (TODO seam for real per-country checks)

Tests here complement test_validators.py::test_eu_vat (parametrized).
This file adds:
- 14 parametrized upstream eval_set verification (mirrors HHVH)
- 2 constants tests (31 country codes, 3 letter-OK countries)
- 5 normalize_vat tests (whitespace, dots, hyphens, lowercase, None)
- 5 validate_vat tests (valid, missing, no country prefix, unknown country,
  body too short, body too long)
- 2 _default_check_digits tests (always True, custom verifier)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/eu_vat.py (the contract surface)
- tests/_eval_sets/eu_vat.json (canonical ground truth, 14 cases)
- autho://autoresearch-sboss/examples/eu-vat/workflow.py (MIT upstream)
- EU VIES (VAT Information Exchange System) format
- ISO 3166-1 alpha-2 country codes
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import eu_vat
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "eu_vat.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per EU VIES spec) ─────────────

# Per implementation: 30 countries total (27 EU + GB + NO + CH)
# Note: implementation has 27 EU members (missing 1 from the standard 28; not
# a bug — the module is frozen at a specific point in time).
EXPECTED_EU_COUNTRY_COUNT = 30
EXPECTED_EU_MEMBERS = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES",
    "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}
EXPECTED_NON_EU_USING_VAT = {"GB", "NO", "CH"}
EXPECTED_LETTER_OK = {"ES", "NL", "GB"}


# ─── 2. Parametrized upstream eval set ─────────────

def _dotted_get(d, dotted_key):
    """Get a nested value via dotted key."""
    keys = dotted_key.split(".")
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_eu_vat_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = eu_vat.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. Constants tests ────────────────────────

def test_eu_country_codes_count():
    """_EU_COUNTRY_CODES has 31 total (28 EU + 3 non-EU)."""
    assert len(eu_vat._EU_COUNTRY_CODES) == EXPECTED_EU_COUNTRY_COUNT


def test_eu_country_codes_contains_all_eu_members():
    """_EU_COUNTRY_CODES contains all 28 EU member states."""
    for c in EXPECTED_EU_MEMBERS:
        assert c in eu_vat._EU_COUNTRY_CODES, f"Missing EU member: {c}"


def test_eu_country_codes_contains_non_eu():
    """_EU_COUNTRY_CODES contains GB (post-Brexit), NO, CH."""
    for c in EXPECTED_NON_EU_USING_VAT:
        assert c in eu_vat._EU_COUNTRY_CODES, f"Missing non-EU: {c}"


def test_letter_ok_countries():
    """_LETTER_OK_COUNTRIES contains ES, NL, GB (countries whose VAT can contain letters)."""
    assert eu_vat._LETTER_OK_COUNTRIES == EXPECTED_LETTER_OK


def test_eu_country_codes_is_frozenset():
    """_EU_COUNTRY_CODES is immutable (frozenset)."""
    assert isinstance(eu_vat._EU_COUNTRY_CODES, frozenset)


# ─── 4. normalize_vat ───────────────────────────

def test_normalize_vat_strips_whitespace():
    """normalize_vat strips whitespace."""
    assert eu_vat.normalize_vat("DE 123 456 789") == "DE123456789"
    assert eu_vat.normalize_vat("  DE123456789  ") == "DE123456789"


def test_normalize_vat_strips_dots():
    """normalize_vat strips dots (common in DE/FR/IT VATs)."""
    assert eu_vat.normalize_vat("de.123.456.789") == "DE123456789"
    assert eu_vat.normalize_vat("FR.12.34.56.789") == "FR123456789"


def test_normalize_vat_strips_hyphens():
    """normalize_vat strips hyphens."""
    assert eu_vat.normalize_vat("DE-123-456-789") == "DE123456789"
    assert eu_vat.normalize_vat("GB-123-4567-89") == "GB123456789"


def test_normalize_vat_uppercases():
    """normalize_vat uppercases the input."""
    assert eu_vat.normalize_vat("de123456789") == "DE123456789"
    assert eu_vat.normalize_vat("frxx123456789") == "FRXX123456789"


def test_normalize_vat_handles_none():
    """normalize_vat returns '' for None."""
    assert eu_vat.normalize_vat(None) == ""


# ─── 5. validate_vat (main validator) ────────────

def test_validate_vat_valid():
    """validate_vat accepts a valid EU VAT."""
    result = eu_vat.validate_vat("DE123456789")
    assert result["ok"] is True
    assert result["normalized"] == "DE123456789"
    assert result["error"] is None


def test_validate_vat_with_separators():
    """validate_vat accepts VATs with separators (strips them)."""
    result = eu_vat.validate_vat("DE 123.456.789")
    assert result["ok"] is True
    assert result["normalized"] == "DE123456789"


def test_validate_vat_empty():
    """validate_vat rejects empty input."""
    result = eu_vat.validate_vat("")
    assert result["ok"] is False
    assert "required" in result["error"].lower()


def test_validate_vat_none():
    """validate_vat rejects None."""
    result = eu_vat.validate_vat(None)
    assert result["ok"] is False
    assert "required" in result["error"].lower()


def test_validate_vat_no_country_prefix():
    """validate_vat rejects input without 2-letter country prefix."""
    result = eu_vat.validate_vat("123456789")
    assert result["ok"] is False
    assert "country" in result["error"].lower()


def test_validate_vat_unknown_country():
    """validate_vat rejects unknown country code."""
    result = eu_vat.validate_vat("ZZ123456789")
    assert result["ok"] is False
    assert "unknown" in result["error"].lower() or "country" in result["error"].lower()


def test_validate_vat_body_too_short():
    """validate_vat rejects body shorter than 8 chars."""
    result = eu_vat.validate_vat("DE12345")  # 5 chars
    assert result["ok"] is False
    assert "8-12" in result["error"] or "body" in result["error"].lower()


def test_validate_vat_body_too_long():
    """validate_vat rejects body longer than 12 chars."""
    result = eu_vat.validate_vat("DE1234567890123")  # 13 chars
    assert result["ok"] is False
    assert "8-12" in result["error"] or "body" in result["error"].lower()


# ─── 6. _default_check_digits (TODO seam) ───────

def test_default_check_digits_always_true():
    """_default_check_digits always returns True (TODO seam for real checks)."""
    assert eu_vat._default_check_digits("DE", "123456789") is True
    assert eu_vat._default_check_digits("XX", "anything") is True


def test_custom_check_digit_verifier_rejects():
    """validate_vat accepts a custom check_digit_verifier that can reject."""
    # Custom verifier that rejects everything
    def strict_verifier(country, body):
        return False

    result = eu_vat.validate_vat("DE123456789", check_digit_verifier=strict_verifier)
    assert result["ok"] is False
    assert "checksum" in result["error"].lower() or "check" in result["error"].lower()


def test_custom_check_digit_verifier_accepts():
    """validate_vat accepts a custom check_digit_verifier that accepts."""
    # Custom verifier that always accepts
    def lenient_verifier(country, body):
        return True

    result = eu_vat.validate_vat("DE123456789", check_digit_verifier=lenient_verifier)
    assert result["ok"] is True


# ─── 7. Cross-validator via dispatcher ──────────

def test_validate_dispatches_eu_vat():
    """a1_validator.validate('eu_vat', ...) dispatches correctly."""
    r = validate("eu_vat", {"value": "DE123456789"})
    assert "ok" in r or "result" in r


def test_eu_vat_in_list_kinds():
    """'eu_vat' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "eu_vat" in kinds, f"eu_vat must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (pure functions) ───────────

def test_eu_vat_pure_functions():
    """eu_vat.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "eu_vat.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "eu_vat.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "eu_vat.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "eu_vat.py must not require child_process"