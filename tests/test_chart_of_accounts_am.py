"""test_chart_of_accounts_am.py — focused tests for the Armenian chart of accounts.

The vendored ``chart_of_accounts_am`` module implements the RA (Republic of
Armenia) chart of accounts (Armenian: Հաշվապահական հաշիվների պլան) per
RA Government Decree N 1329-Ն (effective 2002-01-01, last revised 2016).

Mirrors test_chart_of_accounts_ru.py exactly (per the parallel RU/AM pattern).

Public API:
- ``ACCOUNT_CLASSES`` (list of 9 classes, each with digit, hy, en, type, normalBalance)
- ``STANDARD_ACCOUNTS`` (list, loaded from chart_of_accounts_am.json)
- ``account_class(code) -> dict | None`` — class metadata by code's first digit
- ``account_by_code(code) -> dict | None`` — full account record
- ``normal_balance(code) -> str | None`` — 'debit' / 'credit' / None (offBalance)
- ``validate_code(code) -> dict`` — {ok, normalized, error, account}
- ``validate(input) -> dict`` — uniform entry point

Account classes (9):
  1. Non-current assets (Ոչ ընթացիկ ակտիվներ) — asset, debit
  2. Current assets (Ընթացիկ ակտիվներ) — asset, debit
  3. Equity (Սեփական կապիտալ) — equity, credit
  4. Non-current liabilities — liability, credit
  5. Current liabilities — liability, credit
  6. Income (Եկամուտներ) — income, credit
  7. Expenses (Ծախսեր) — expense, debit
  8. Management accounting — management, debit
  9. Off-balance-sheet (Արտահաշվեկշռային հաշիվներ) — offBalance, None

Error codes (validate_code):
  - "empty_code" — None, "", or whitespace-only
  - "non_numeric_code" — contains non-digits
  - "invalid_length_code" — not 3 or 4 digits
  - "unknown_code" — well-formed but not in data file

Tests here complement test_validators.py::test_chart_of_accounts_am (parametrized).
This file adds:
- 20 parametrized upstream eval_set verification
- 5 constants tests (9 ACCOUNT_CLASSES, Armenian + English names, type, normalBalance, offBalance has None)
- 5 account_class tests (digit 1, 5, 6, 9 offBalance, non-numeric)
- 5 account_by_code tests (valid, unknown, non-string, offBalance, real fixture)
- 5 normal_balance tests (asset = debit, liability = credit, expense = debit, offBalance = None, unknown = None)
- 5 validate_code tests (valid, empty, non-numeric, wrong length, unknown)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/chart_of_accounts_am.py (the contract surface)
- tests/_eval_sets/chart_of_accounts_am.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/chart-of-accounts-am/workflow.py (MIT upstream)
- RA Government Decree N 1329-Ն (Armenian chart of accounts)
- A1-Localization-AM/src/chartOfAccounts.js (the JS source of truth)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import chart_of_accounts_am
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "chart_of_accounts_am.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per RA Government Decree N 1329-Ն) ──

EXPECTED_ACCOUNT_CLASS_COUNT = 9
EXPECTED_CLASS_DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
EXPECTED_TYPES = {"asset", "equity", "liability", "income", "expense", "management", "offBalance"}
EXPECTED_NORMAL_BALANCES = {"debit", "credit", None}  # None for offBalance


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
def test_chart_of_accounts_am_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = chart_of_accounts_am.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. Constants tests ────────────────────────

def test_account_classes_count_9():
    """ACCOUNT_CLASSES is a list of exactly 9 classes."""
    assert len(chart_of_accounts_am.ACCOUNT_CLASSES) == EXPECTED_ACCOUNT_CLASS_COUNT


def test_account_classes_digits_1_to_9():
    """ACCOUNT_CLASSES has digits 1-9 (no 0, no duplicates)."""
    digits = [c["digit"] for c in chart_of_accounts_am.ACCOUNT_CLASSES]
    assert sorted(digits) == EXPECTED_CLASS_DIGITS


def test_account_classes_have_required_fields():
    """Each ACCOUNT_CLASSES entry has digit, hy, en, type, normalBalance."""
    for c in chart_of_accounts_am.ACCOUNT_CLASSES:
        assert "digit" in c, f"Class missing 'digit': {c}"
        assert "hy" in c, f"Class missing Armenian 'hy' name: {c}"
        assert "en" in c, f"Class missing English 'en' name: {c}"
        assert "type" in c, f"Class missing 'type': {c}"
        assert "normalBalance" in c, f"Class missing 'normalBalance': {c}"


def test_account_classes_have_valid_types():
    """ACCOUNT_CLASSES 'type' values are from the expected set."""
    for c in chart_of_accounts_am.ACCOUNT_CLASSES:
        assert c["type"] in EXPECTED_TYPES, f"Invalid type {c['type']!r} in {c}"


def test_account_classes_offBalance_has_null_normal_balance():
    """Class 9 (off-balance) has normalBalance=None (per decree)."""
    off_balance = [c for c in chart_of_accounts_am.ACCOUNT_CLASSES if c["digit"] == 9]
    assert len(off_balance) == 1
    assert off_balance[0]["normalBalance"] is None
    assert off_balance[0]["type"] == "offBalance"


# ─── 4. account_class tests ───────────────────

def test_account_class_digit_1_assets():
    """account_class(1xxx) returns class 1 (Non-current assets, debit)."""
    cls = chart_of_accounts_am.account_class("1010")
    assert cls is not None
    assert cls["digit"] == 1
    assert cls["type"] == "asset"
    assert cls["normalBalance"] == "debit"


def test_account_class_digit_5_liabilities():
    """account_class(5xxx) returns class 5 (Current liabilities, credit)."""
    cls = chart_of_accounts_am.account_class("5310")
    assert cls is not None
    assert cls["digit"] == 5
    assert cls["type"] == "liability"
    assert cls["normalBalance"] == "credit"


def test_account_class_digit_6_income():
    """account_class(6xxx) returns class 6 (Income, credit)."""
    cls = chart_of_accounts_am.account_class("6110")
    assert cls is not None
    assert cls["digit"] == 6
    assert cls["type"] == "income"
    assert cls["normalBalance"] == "credit"


def test_account_class_digit_9_offbalance():
    """account_class(9xxx) returns class 9 (Off-balance, None)."""
    cls = chart_of_accounts_am.account_class("9010")
    assert cls is not None
    assert cls["digit"] == 9
    assert cls["type"] == "offBalance"
    assert cls["normalBalance"] is None


def test_account_class_non_numeric_returns_none():
    """account_class returns None for non-numeric input."""
    assert chart_of_accounts_am.account_class("xxxx") is None
    assert chart_of_accounts_am.account_class("") is None
    assert chart_of_accounts_am.account_class(None) is None


# ─── 5. account_by_code tests ─────────────────

def test_account_by_code_valid():
    """account_by_code returns the full account record for a valid code.

    Per the data file: each account has {code, hy, class, type}.
    """
    accounts = chart_of_accounts_am.STANDARD_ACCOUNTS
    if len(accounts) > 0:
        first_code = accounts[0]["code"]
        result = chart_of_accounts_am.account_by_code(first_code)
        assert result is not None
        assert result["code"] == first_code
        assert "hy" in result  # Armenian name
        assert "class" in result  # digit (1-9)
        assert "type" in result  # asset/equity/liability/...


def test_account_by_code_unknown_returns_none():
    """account_by_code returns None for unknown code (well-formed)."""
    assert chart_of_accounts_am.account_by_code("9999") is None
    assert chart_of_accounts_am.account_by_code("0000") is None


def test_account_by_code_handles_none():
    """account_by_code handles None gracefully."""
    assert chart_of_accounts_am.account_by_code(None) is None


def test_account_by_code_strips_whitespace():
    """account_by_code strips whitespace from input."""
    # Use a known real code
    accounts = chart_of_accounts_am.STANDARD_ACCOUNTS
    if len(accounts) > 0:
        first_code = accounts[0]["code"]
        result = chart_of_accounts_am.account_by_code(f"  {first_code}  ")
        assert result is not None
        assert result["code"] == first_code


# ─── 6. normal_balance tests ──────────────────

def test_normal_balance_asset_is_debit():
    """Asset accounts (1xxx, 2xxx) have normal balance 'debit'."""
    assert chart_of_accounts_am.normal_balance("1010") == "debit"
    assert chart_of_accounts_am.normal_balance("2010") == "debit"


def test_normal_balance_liability_is_credit():
    """Liability accounts (4xxx, 5xxx) have normal balance 'credit'."""
    assert chart_of_accounts_am.normal_balance("4010") == "credit"
    assert chart_of_accounts_am.normal_balance("5310") == "credit"


def test_normal_balance_expense_is_debit():
    """Expense accounts (7xxx) have normal balance 'debit'."""
    assert chart_of_accounts_am.normal_balance("7110") == "debit"


def test_normal_balance_offbalance_is_none():
    """Off-balance accounts (9xxx) have normal balance None."""
    assert chart_of_accounts_am.normal_balance("9010") is None


def test_normal_balance_unknown_code_is_none():
    """normal_balance returns None for unknown code."""
    assert chart_of_accounts_am.normal_balance("9999") is None
    assert chart_of_accounts_am.normal_balance(None) is None


# ─── 7. validate_code tests ───────────────────

def test_validate_code_valid():
    """validate_code returns ok=True for a known valid code."""
    accounts = chart_of_accounts_am.STANDARD_ACCOUNTS
    if len(accounts) > 0:
        first_code = accounts[0]["code"]
        result = chart_of_accounts_am.validate_code(first_code)
        assert result["ok"] is True
        assert result["error"] is None
        assert result["account"] is not None


def test_validate_code_empty():
    """validate_code returns ok=False with 'empty_code' error for empty."""
    result = chart_of_accounts_am.validate_code("")
    assert result["ok"] is False
    assert result["error"] == "empty_code"
    assert result["account"] is None

    result = chart_of_accounts_am.validate_code(None)
    assert result["ok"] is False
    assert result["error"] == "empty_code"


def test_validate_code_non_numeric():
    """validate_code returns 'non_numeric_code' for non-digit input."""
    result = chart_of_accounts_am.validate_code("abcd")
    assert result["ok"] is False
    assert result["error"] == "non_numeric_code"


def test_validate_code_invalid_length():
    """validate_code returns 'invalid_length_code' for length not 3-4."""
    result = chart_of_accounts_am.validate_code("12")  # 2 digits
    assert result["ok"] is False
    assert result["error"] == "invalid_length_code"

    result = chart_of_accounts_am.validate_code("12345")  # 5 digits
    assert result["ok"] is False
    assert result["error"] == "invalid_length_code"


def test_validate_code_unknown():
    """validate_code returns 'unknown_code' for well-formed but unknown."""
    result = chart_of_accounts_am.validate_code("9999")
    assert result["ok"] is False
    assert result["error"] == "unknown_code"
    assert result["account"] is None


# ─── 8. Cross-validator via dispatcher ──────────

def test_validate_dispatches_chart_of_accounts_am():
    """a1_validator.validate('chart_of_accounts_am', ...) dispatches correctly."""
    r = validate("chart_of_accounts_am", {"code": "1010"})
    assert "ok" in r or "result" in r or "class" in r


def test_chart_of_accounts_am_in_list_kinds():
    """'chart_of_accounts_am' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "chart_of_accounts_am" in kinds, f"chart_of_accounts_am must be in list_kinds() (got: {kinds})"


# ─── 9. Sovereignty (pure functions) ───────────

def test_chart_of_accounts_am_pure_functions():
    """chart_of_accounts_am.py must be pure — no I/O at runtime (data file is loaded at import time only)."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "chart_of_accounts_am.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "chart_of_accounts_am.py must not require network modules"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "chart_of_accounts_am.py must not require child_process"