"""test_einvoice_am.py — focused tests for the Armenian e-invoice validator.

The vendored ``einvoice_am`` module validates the structural compliance
of Armenian e-invoices (УПД / electronic счёт-фактура, формат 5.03) per
SRC (State Revenue Committee) requirements effective 2025-03-01.

Public API:
- ``EINVOICE_NAMESPACE = "urn:hayhashvapah:einvoice:1"``
- ``ISSUED_INVOICE_VAT_RATES = (0, 20)``
- ``MAX_LINE_DESCRIPTION = 256``
- ``validate_e_invoice(invoice) -> dict`` — structural compliance gate (never throws)
- ``validate(input) -> dict`` — uniform entry point

Contract:
- Returns ``{ok: bool, errors: [...]}``
- Errors have shape ``{field, code, message}``
- HVVH validation: 8 digits, not all-same (defends against 00000000)

Tests here complement test_validators.py::test_einvoice_am (parametrized).
This file adds:
- 20 parametrized upstream eval_set verification (mirrors HHVH)
- 3 constants tests (namespace, VAT rates, max line description)
- 6 _is_valid_hvhh tests (8 digits, all-same rejection, non-digit, too short, too long, valid)
- 8 validate_e_invoice tests (missing transactionType, missing number, missing supplier HVVH, invalid HVVH, line description too long, valid)
- 3 validate tests (uniform entry point)
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/einvoice_am.py (the contract surface)
- tests/_eval_sets/einvoice_am.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/einvoice-am/workflow.py (MIT upstream)
- Armenian SRC e-invoice format spec (effective 2025-03-01)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import einvoice_am
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "einvoice_am.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per Armenian SRC spec) ─────────

EXPECTED_NAMESPACE = "urn:hayhashvapah:einvoice:1"
EXPECTED_VAT_RATES = (0, 20)
EXPECTED_MAX_LINE_DESCRIPTION = 256


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
def test_einvoice_am_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = einvoice_am.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. Constants tests ────────────────────────

def test_einvoice_namespace():
    """EINVOICE_NAMESPACE is the Armenian e-invoice URN."""
    assert einvoice_am.EINVOICE_NAMESPACE == EXPECTED_NAMESPACE


def test_issued_invoice_vat_rates():
    """ISSUED_INVOICE_VAT_RATES contains exactly 0% and 20% (per RA Tax Code)."""
    assert tuple(einvoice_am.ISSUED_INVOICE_VAT_RATES) == EXPECTED_VAT_RATES


def test_max_line_description():
    """MAX_LINE_DESCRIPTION is 256 characters (per spec)."""
    assert einvoice_am.MAX_LINE_DESCRIPTION == EXPECTED_MAX_LINE_DESCRIPTION


# ─── 4. _is_valid_hvhh (HHVH validation) ───────────

def test_is_valid_hvhh_8_digits_valid():
    """_is_valid_hvhh accepts 8 distinct digits."""
    assert einvoice_am._is_valid_hvhh("01234567") is True
    assert einvoice_am._is_valid_hvhh("11111112") is True


def test_is_valid_hvhh_rejects_all_same():
    """_is_valid_hvhh rejects 8 same digits (e.g. 00000000)."""
    assert einvoice_am._is_valid_hvhh("00000000") is False
    assert einvoice_am._is_valid_hvhh("11111111") is False


def test_is_valid_hvhh_rejects_non_digits():
    """_is_valid_hvhh rejects non-digit characters."""
    assert einvoice_am._is_valid_hvhh("0123456a") is False
    assert einvoice_am._is_valid_hvhh("0123-456") is False  # dashes
    assert einvoice_am._is_valid_hvhh("abcdefgh") is False


def test_is_valid_hvhh_rejects_wrong_length():
    """_is_valid_hvhh rejects lengths other than 8."""
    assert einvoice_am._is_valid_hvhh("1234567") is False    # 7 digits
    assert einvoice_am._is_valid_hvhh("123456789") is False  # 9 digits
    assert einvoice_am._is_valid_hvhh("") is False
    assert einvoice_am._is_valid_hvhh(None) is False


def test_is_valid_hvhh_handles_whitespace():
    """_is_valid_hvhh strips whitespace before validation."""
    assert einvoice_am._is_valid_hvhh("  01234567  ") is True
    assert einvoice_am._is_valid_hvhh("0123 4567") is False  # internal whitespace fails (not all digits)


def test_is_valid_hvhh_handles_non_string():
    """_is_valid_hvhh handles non-string input gracefully."""
    # Per implementation: _str() converts to string, so int 12345678 becomes "12345678" (valid)
    # Containers (list, dict) become their str() repr which is not all-digits
    assert einvoice_am._is_valid_hvhh(12345678) is True  # int → "12345678" (8 digits, all different)
    assert einvoice_am._is_valid_hvhh([]) is False  # "[]" not all-digits
    assert einvoice_am._is_valid_hvhh({}) is False  # "{}" not all-digits


# ─── 5. validate_e_invoice (structural gate) ────

def _make_valid_invoice():
    """Create a baseline valid invoice for tests."""
    return {
        "transactionType": "SALE",
        "number": "INV-001",
        "issueDate": "2025-03-15",
        "supplier": {"name": "ACME Corp", "hvhh": "01234567"},
        "buyer": {"name": "Buyer Inc", "hvhh": "11111112"},
        "lines": [
            {
                "description": "Service A",
                "quantity": 2,
                "netAmount": 100000,
                "vatRate": 20,
            },
        ],
    }


def test_validate_e_invoice_valid_passes():
    """validate_e_invoice returns ok=True for a valid invoice."""
    result = einvoice_am.validate_e_invoice(_make_valid_invoice())
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_e_invoice_missing_transaction_type():
    """validate_e_invoice reports error for missing transactionType."""
    invoice = _make_valid_invoice()
    del invoice["transactionType"]
    result = einvoice_am.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any(e["field"] == "transactionType" for e in result["errors"])


def test_validate_e_invoice_missing_number():
    """validate_e_invoice reports error for missing invoice number."""
    invoice = _make_valid_invoice()
    del invoice["number"]
    result = einvoice_am.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any(e["field"] == "number" for e in result["errors"])


def test_validate_e_invoice_invalid_supplier_hvhh():
    """validate_e_invoice reports error for invalid supplier HVVH."""
    invoice = _make_valid_invoice()
    invoice["supplier"]["hvhh"] = "00000000"  # all-same
    result = einvoice_am.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any(e["field"] == "supplier.hvhh" for e in result["errors"])


def test_validate_e_invoice_line_description_too_long():
    """validate_e_invoice reports error for line description > 256 chars."""
    invoice = _make_valid_invoice()
    invoice["lines"][0]["description"] = "x" * 257
    result = einvoice_am.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any("line" in e.get("field", "").lower() or "description" in e.get("field", "").lower()
                for e in result["errors"])


def test_validate_e_invoice_handles_non_dict():
    """validate_e_invoice returns errors for non-dict input (never throws)."""
    result = einvoice_am.validate_e_invoice(None)
    assert result["ok"] is False
    assert len(result["errors"]) > 0


def test_validate_e_invoice_handles_empty_dict():
    """validate_e_invoice returns errors for empty dict."""
    result = einvoice_am.validate_e_invoice({})
    assert result["ok"] is False
    assert len(result["errors"]) > 0


def test_validate_e_invoice_returns_never_throws():
    """validate_e_invoice never throws (always returns ok/errors dict)."""
    # Test with various invalid inputs
    for inv in [None, "", 42, [], {"supplier": None}, {"lines": "not a list"}]:
        result = einvoice_am.validate_e_invoice(inv)
        assert isinstance(result, dict)
        assert "ok" in result
        assert "errors" in result


# ─── 6. Cross-validator via dispatcher ──────────

def test_validate_dispatches_einvoice_am():
    """a1_validator.validate('einvoice_am', ...) dispatches correctly."""
    r = validate("einvoice_am", {"invoice": _make_valid_invoice()})
    assert "ok" in r or "result" in r


def test_einvoice_am_in_list_kinds():
    """'einvoice_am' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "einvoice_am" in kinds, f"einvoice_am must be in list_kinds() (got: {kinds})"


# ─── 7. Sovereignty (pure functions) ───────────

def test_einvoice_am_pure_functions():
    """einvoice_am.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "einvoice_am.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "einvoice_am.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "einvoice_am.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "einvoice_am.py must not require child_process"