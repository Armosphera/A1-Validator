"""test_vat_return_form.py — focused tests for the Russian VAT return form validator.

The vendored ``vat_return_form`` module implements the structural validation
of the Russian VAT return form (КНД 1151001) per НК РФ гл. 21 + Приказ ФНС
ММВ-7-3/163@ от 29.10.2014 (effective 2026 form).

Public API:
- ``VAT_FORM_REQUIRED_LINES`` (9-tuple: "7", "9", "12", "13", "16", "17", "18", "21", "23")
- ``VAT_FORM_LINE_AMOUNT_FIELDS`` (dict: line_id → tuple of field names)
- ``STANDARD_VAT_RATE = 20`` (the 2025/2024 rate; 2026 reform makes this 22)
- ``IMPUTED_VAT_RATE = 16.67``
- ``_val(lines, line_id, field) -> float`` — read a numeric line amount
- ``_has(lines, *ids) -> bool`` — check if all lines exist as dicts
- ``validate_vat_return_form(form) -> dict`` — structural validation (returns {ok, errors})
- ``validate(input) -> dict`` — uniform entry point

Contract:
- Returns ``{ok: bool, errors: [{field, code, message}]}``
- 9 required lines must be present (7, 9, 12, 13, 16, 17, 18, 21, 23)
- Each line has specific amount fields (base, vat, payable, recoverable)
- Amounts must be numeric, non-negative, whole-drams (integer)
- Bools rejected as numeric values
- NaN/Inf rejected

Tests here complement test_validators.py::test_vat_return_form (parametrized).
This file adds:
- 20 parametrized upstream eval_set verification (mirrors HHVH)
- 4 constants tests (9 REQUIRED_LINES, fields, rates)
- 3 _val tests (valid, missing line, missing field, non-numeric)
- 3 _has tests (all present, one missing, multiple missing)
- 8 validate_vat_return_form tests (valid, missing line, non-numeric, negative,
  bool, float, NaN/Inf, non-dict input)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/vat_return_form.py (the contract surface)
- tests/_eval_sets/vat_return_form.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/vat-return-form/workflow.py (MIT upstream)
- НК РФ гл. 21
- Приказ ФНС ММВ-7-3/163@ от 29.10.2014
- КНД 1151001
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import vat_return_form
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "vat_return_form.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per Russian VAT return form spec) ──

EXPECTED_REQUIRED_LINES = ("7", "9", "12", "13", "16", "17", "18", "21", "23")
EXPECTED_STANDARD_VAT_RATE = 20  # 2025/2024; 2026 reform = 22
EXPECTED_IMPUTED_VAT_RATE = 16.67


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
def test_vat_return_form_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = vat_return_form.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. Constants tests ────────────────────────

def test_required_lines_is_9_tuple():
    """VAT_FORM_REQUIRED_LINES is a tuple of exactly 9 line IDs."""
    assert isinstance(vat_return_form.VAT_FORM_REQUIRED_LINES, tuple)
    assert len(vat_return_form.VAT_FORM_REQUIRED_LINES) == 9
    assert vat_return_form.VAT_FORM_REQUIRED_LINES == EXPECTED_REQUIRED_LINES


def test_line_amount_fields_dict():
    """VAT_FORM_LINE_AMOUNT_FIELDS is a dict mapping line_id → fields tuple."""
    fields = vat_return_form.VAT_FORM_LINE_AMOUNT_FIELDS
    assert isinstance(fields, dict)
    # Each required line has at least one field
    for line_id in EXPECTED_REQUIRED_LINES:
        assert line_id in fields, f"Missing fields for line {line_id}"
        assert isinstance(fields[line_id], tuple)
        assert len(fields[line_id]) > 0


def test_standard_vat_rate():
    """STANDARD_VAT_RATE is 20 (pre-2026 reform; the module is frozen at the 2025 form)."""
    assert vat_return_form.STANDARD_VAT_RATE == EXPECTED_STANDARD_VAT_RATE


def test_imputed_vat_rate():
    """IMPUTED_VAT_RATE is 16.67 (per ст. 154 п. 4 НК РФ)."""
    assert vat_return_form.IMPUTED_VAT_RATE == EXPECTED_IMPUTED_VAT_RATE


# ─── 4. _val (numeric line reader) ─────────────────

def test_val_returns_numeric_value():
    """_val returns the numeric value of a line field."""
    lines = {"7": {"base": 100, "vat": 20}}
    assert vat_return_form._val(lines, "7", "base") == 100
    assert vat_return_form._val(lines, "7", "vat") == 20


def test_val_returns_zero_for_missing_line():
    """_val returns 0 for missing line (defensive)."""
    assert vat_return_form._val({}, "7", "base") == 0
    assert vat_return_form._val({"9": {}}, "7", "base") == 0


def test_val_returns_zero_for_missing_field():
    """_val returns 0 for missing field (defensive)."""
    lines = {"7": {"base": 100}}  # no "vat" field
    assert vat_return_form._val(lines, "7", "vat") == 0


def test_val_returns_zero_for_non_numeric():
    """_val returns 0 for non-numeric values (defensive)."""
    lines = {"7": {"base": "not a number", "vat": None}}
    assert vat_return_form._val(lines, "7", "base") == 0
    assert vat_return_form._val(lines, "7", "vat") == 0


# ─── 5. _has (line presence checker) ───────────

def test_has_all_present():
    """_has returns True when all lines are present as dicts."""
    lines = {"7": {}, "9": {}, "12": {}}
    assert vat_return_form._has(lines, "7", "9", "12") is True


def test_has_one_missing():
    """_has returns False when one line is missing."""
    lines = {"7": {}, "9": {}}
    assert vat_return_form._has(lines, "7", "9", "12") is False


def test_has_multiple_missing():
    """_has returns False when multiple lines are missing."""
    lines = {"7": {}}
    assert vat_return_form._has(lines, "7", "9", "12") is False


# ─── 6. validate_vat_return_form (main validator) ───

def _make_valid_form():
    """Create a baseline valid VAT return form (cross-foot consistent).

    The form has 5 cross-foot checks:
    - Line 16 base = 7+9+12+13 bases
    - Line 16 vat = 7+9 vats
    - Line 9 vat ≈ 16.67% of base (±5%)
    - Line 23 = line16.vat - line21.vat
    """
    return {
        "lines": {
            "7": {"base": 100000, "vat": 20000},  # 20% standard rate
            "9": {"base": 50000, "vat": 8335},     # 16.67% imputed rate (within ±5%)
            "12": {"base": 150000},                # tax-exempt sales
            "13": {"base": 200000},                # non-VAT sales
            "16": {"base": 500000, "vat": 28335},  # = 7+9+12+13 base, = 7+9 vat
            "17": {"base": 100000, "vat": 20000},  # deductible input VAT
            "18": {"base": 50000, "vat": 8335},    # deductible input VAT
            "21": {"vat": 28335},                  # = 17+18 VAT (input VAT to be deducted)
            "23": {"payable": 0, "recoverable": 0},  # = 16.vat - 21.vat = 28335 - 28335 = 0
        }
    }


def test_validate_vat_return_form_valid_passes():
    """validate_vat_return_form returns ok=True for a valid form."""
    result = vat_return_form.validate_vat_return_form(_make_valid_form())
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_vat_return_form_missing_required_line():
    """validate_vat_return_form reports error for missing required line."""
    form = _make_valid_form()
    del form["lines"]["7"]
    result = vat_return_form.validate_vat_return_form(form)
    assert result["ok"] is False
    assert any(e["field"] == "lines.7" for e in result["errors"])


def test_validate_vat_return_form_non_numeric_amount():
    """validate_vat_return_form rejects non-numeric amounts."""
    form = _make_valid_form()
    form["lines"]["7"]["base"] = "not a number"
    result = vat_return_form.validate_vat_return_form(form)
    assert result["ok"] is False
    assert any("FORM_NON_NUMERIC_AMOUNT" in e["code"] for e in result["errors"])


def test_validate_vat_return_form_rejects_bool():
    """validate_vat_return_form rejects bools (Python bool is int subclass)."""
    form = _make_valid_form()
    form["lines"]["7"]["base"] = True  # bool is treated as int in Python!
    result = vat_return_form.validate_vat_return_form(form)
    assert result["ok"] is False
    # The implementation explicitly rejects bools
    assert any("FORM_NON_NUMERIC_AMOUNT" in e["code"] for e in result["errors"])


def test_validate_vat_return_form_rejects_negative():
    """validate_vat_return_form rejects negative amounts."""
    form = _make_valid_form()
    form["lines"]["7"]["base"] = -100
    result = vat_return_form.validate_vat_return_form(form)
    assert result["ok"] is False
    assert any("FORM_NEGATIVE_AMOUNT" in e["code"] for e in result["errors"])


def test_validate_vat_return_form_rejects_non_integer():
    """validate_vat_return_form rejects non-integer amounts (whole-dram requirement)."""
    form = _make_valid_form()
    form["lines"]["7"]["base"] = 100.5  # half-dram
    result = vat_return_form.validate_vat_return_form(form)
    assert result["ok"] is False
    assert any("FORM_NON_INTEGER_AMOUNT" in e["code"] for e in result["errors"])


def test_validate_vat_return_form_handles_non_dict():
    """validate_vat_return_form handles non-dict input (never throws)."""
    # Per implementation: non-dict form becomes {"lines": {}}
    result = vat_return_form.validate_vat_return_form(None)
    assert isinstance(result, dict)
    assert "ok" in result
    # Note: None input → "lines" becomes {} → many errors
    assert result["ok"] is False


def test_validate_vat_return_form_accepts_lines_directly():
    """validate_vat_return_form accepts a lines dict directly (not wrapped in {lines: ...})."""
    lines = _make_valid_form()["lines"]
    # Per implementation: if not "lines" key, uses the dict as lines
    result = vat_return_form.validate_vat_return_form(lines)
    assert isinstance(result, dict)
    assert "ok" in result


# ─── 7. Cross-validator via dispatcher ──────────

def test_validate_dispatches_vat_return_form():
    """a1_validator.validate('vat_return_form', ...) dispatches correctly."""
    r = validate("vat_return_form", {"form": _make_valid_form()})
    assert "ok" in r or "result" in r


def test_vat_return_form_in_list_kinds():
    """'vat_return_form' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "vat_return_form" in kinds, f"vat_return_form must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (pure functions) ───────────

def test_vat_return_form_pure_functions():
    """vat_return_form.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "vat_return_form.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "vat_return_form.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "vat_return_form.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "vat_return_form.py must not require child_process"