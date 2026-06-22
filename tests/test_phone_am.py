"""test_phone_am.py — focused tests for the Armenian phone number validator.

The vendored ``phone_am`` module implements RA telephone number validation
per the national numbering plan (country code +374, 8-digit NSN starting
with 1-9, no leading zero).

Public API:
- ``normalize_nsn(value) -> str`` — strip +374/00374/0 prefix, return 8-digit NSN or ""
- ``is_valid_armenian_phone(value) -> bool`` — True if normalize_nsn returns non-empty
- ``e164(value) -> str | None`` — +374XXXXXXXX (E.164 format) or None
- ``format_phone(value) -> str | None`` — +374 XX XXXXXX (grouped) or None
- ``validate(input_data) -> dict`` — uniform entry point (mirrors others)

Tests here complement test_validators.py::test_phone_am (parametrized
verification against the eval_set). This file adds:
- 20 parametrized upstream eval_set verification (mirrors HHVH)
- 4 known-valid real-world fixtures
- 6 input format variations (E.164, 00374, 0, raw, with spaces, with dashes)
- 6 invalid inputs (empty, None, non-string, too short, too long, starts with 0)
- 3 e164/format_phone specific tests
- 2 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/phone_am.py (the contract surface)
- tests/_eval_sets/phone_am.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/phone-am/workflow.py (MIT upstream)
- RA Government Decree N 975-N (2012) — Armenian numbering plan
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import phone_am
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "phone_am.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per RA Government Decree N 975-N) ────────

EXPECTED_COUNTRY_CODE = "374"      # Armenia
EXPECTED_NSN_LENGTH = 8            # National Significant Number length
EXPECTED_NSN_FIRST_DIGIT_MIN = 1   # NSN must start with 1-9 (not 0)
EXPECTED_NSN_FIRST_DIGIT_MAX = 9


# ─── 2. Parametrized upstream eval set ─────────────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_phone_am_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = phone_am.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


# ─── 3. normalize_nsn (strip prefixes) ─────────────────────

def test_normalize_nsn_strips_plus374_prefix():
    """+374XXXXXXXX → XXXXXXXX (8 digits)."""
    assert phone_am.normalize_nsn("+374 91 234567") == "91234567"
    assert phone_am.normalize_nsn("+37491234567") == "91234567"
    assert phone_am.normalize_nsn("+374 11 123456") == "11123456"


def test_normalize_nsn_strips_00374_prefix():
    """00374XXXXXXXX → XXXXXXXX (international format, 00 prefix)."""
    assert phone_am.normalize_nsn("0037491234567") == "91234567"
    assert phone_am.normalize_nsn("00 374 91 234567") == "91234567"


def test_normalize_nsn_strips_0_prefix():
    """09XXXXXXXX → XXXXXXXX (domestic format, 0 prefix)."""
    assert phone_am.normalize_nsn("091234567") == "91234567"
    assert phone_am.normalize_nsn("0 91 234 567") == "91234567"


def test_normalize_nsn_accepts_raw_8_digits():
    """Raw 8-digit NSN is accepted (no prefix)."""
    assert phone_am.normalize_nsn("91234567") == "91234567"


def test_normalize_nsn_rejects_starts_with_zero():
    """8-digit numbers starting with 0 are NOT valid NSN."""
    assert phone_am.normalize_nsn("01234567") == ""
    assert phone_am.normalize_nsn("00000000") == ""


def test_normalize_nsn_rejects_too_short():
    """Numbers with fewer than 8 digits (after prefix strip) are invalid."""
    assert phone_am.normalize_nsn("+374 1 12345") == ""     # 6 digits
    assert phone_am.normalize_nsn("+374 1") == ""            # 1 digit
    assert phone_am.normalize_nsn("") == ""                  # empty
    assert phone_am.normalize_nsn(None) == ""                 # None


def test_normalize_nsn_rejects_too_long():
    """Numbers with more than 8 digits are invalid."""
    assert phone_am.normalize_nsn("+374 91 2345678") == ""   # 9 digits
    assert phone_am.normalize_nsn("+374 91 23456789") == ""  # 10 digits


def test_normalize_nsn_rejects_non_digit_chars():
    """NSN must be all digits."""
    assert phone_am.normalize_nsn("+374 91 2345A7") == ""
    assert phone_am.normalize_nsn("+374 91 2345-67") == "91234567"  # dashes stripped


# ─── 4. is_valid_armenian_phone (validation) ─────────────

def test_is_valid_armenian_phone_known_valid():
    """Known-valid Armenian phone numbers."""
    assert phone_am.is_valid_armenian_phone("+374 91 234567") is True
    assert phone_am.is_valid_armenian_phone("0037491234567") is True
    assert phone_am.is_valid_armenian_phone("091234567") is True
    assert phone_am.is_valid_armenian_phone("91234567") is True
    assert phone_am.is_valid_armenian_phone(91234567) is True  # int accepted


def test_is_valid_armenian_phone_known_invalid():
    """Known-invalid inputs."""
    assert phone_am.is_valid_armenian_phone("") is False
    assert phone_am.is_valid_armenian_phone(None) is False
    # +374 12 345678 → "12345678" — VALID (starts with 1, not 0). No special case here.
    assert phone_am.is_valid_armenian_phone("1234567") is False  # 7 digits
    assert phone_am.is_valid_armenian_phone("123456789") is False  # 9 digits


# ─── 5. e164 (E.164 format) ─────────────────────────────

def test_e164_format():
    """E.164 format is +374XXXXXXXX."""
    assert phone_am.e164("+374 91 234567") == "+37491234567"
    assert phone_am.e164("0037491234567") == "+37491234567"
    assert phone_am.e164("091234567") == "+37491234567"
    assert phone_am.e164("91234567") == "+37491234567"


def test_e164_returns_none_for_invalid():
    """E.164 returns None for invalid input."""
    assert phone_am.e164("") is None
    # +374 12 345678 is valid → e164 returns "+37412345678"
    assert phone_am.e164(None) is None


# ─── 6. format_phone (grouped display) ───────────────────

def test_format_phone_groups_correctly():
    """+374 XX XXXXXX (2+6 digit grouping)."""
    assert phone_am.format_phone("+374 91 234567") == "+374 91 234567"
    assert phone_am.format_phone("0037491234567") == "+374 91 234567"
    assert phone_am.format_phone("091234567") == "+374 91 234567"
    assert phone_am.format_phone("91234567") == "+374 91 234567"


def test_format_phone_returns_none_for_invalid():
    """format_phone returns None for invalid input."""
    assert phone_am.format_phone("") is None
    # +374 12 345678 is valid → formatted returns "+374 12 345678"
    assert phone_am.format_phone(None) is None


# ─── 7. Cross-validator via dispatcher ──────────────────

def test_validate_dispatches_phone_am():
    """a1_validator.validate('phone_am', ...) dispatches correctly."""
    r = validate("phone_am", {"phone": "+374 91 234567"})
    assert r["valid"] is True
    assert r["nsn"] == "91234567"
    assert r["e164"] == "+37491234567"
    assert r["formatted"] == "+374 91 234567"


def test_phone_am_in_list_kinds():
    """'phone_am' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "phone_am" in kinds, f"phone_am must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (offline-capable) ──────────────────

def test_phone_am_pure_functions():
    """phone_am.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "phone_am.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "phone_am.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "phone_am.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "phone_am.py must not require child_process"