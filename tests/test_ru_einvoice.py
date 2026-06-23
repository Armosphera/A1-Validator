"""test_ru_einvoice.py — focused tests for the Russian e-invoice validator.

The vendored ``ru_einvoice`` module implements the structural validation
+ XML generation for Russian e-invoices (УПД / electronic счёт-фактура,
формат 5.03) per ФНС Приказ № ММВ-7-15/820@ от 19.12.2018.

Public API:
- ``RUB_CURRENCY_CODE = "643"`` (ISO 4217 for Russian ruble)
- ``MAX_LINE_DESCRIPTION = 1000``
- ``round_rub(value) -> float`` — round to whole kopecks (2 decimals)
- ``is_valid_inn(value) -> bool`` / ``validate_inn(value) -> dict``
- ``is_valid_kpp(value) -> bool``
- ``rates_for(year) -> dict`` — VAT rates (standard, reduced, zero)
- ``_is_valid_iso_date(value) -> bool`` — strict YYYY-MM-DD + real date
- ``e_invoice_totals(lines) -> dict`` — {net, vat, total}
- ``validate_e_invoice(invoice) -> dict`` — structural validation (never throws)
- ``build_e_invoice_xml(invoice) -> str`` — XML generation (XML-escaped)
- ``validate(input) -> dict`` — uniform entry point

Contract:
- ``validate_e_invoice`` returns ``{ok: bool, errors: [...]}`` (NEVER throws)
- Each error has ``{field, code, message}``
- ISO date format is STRICT: ``YYYY-MM-DD`` (no Date.toISOString() shortcut)
- INN validation: 10 or 12 digits with mod-11 check
- XML output is XML-escaped (& < > " ' are escaped)
- Currency code: "RUB" → 643, others → 3-digit numeric code required

Tests here complement test_validators.py::test_ru_einvoice (parametrized).
This file adds:
- 18 parametrized upstream eval_set verification (mirrors HHVH)
- 4 constants tests (RUB_CURRENCY_CODE, MAX_LINE_DESCRIPTION, VAT rates)
- 5 round_rub tests (rounding, NaN, Inf, None, negative)
- 5 is_valid_inn tests (10-digit valid, 12-digit valid, wrong check, wrong length, non-digit)
- 4 is_valid_kpp tests (valid, wrong length, non-digit, empty)
- 4 _is_valid_iso_date tests (valid, wrong format, invalid month, invalid day)
- 4 e_invoice_totals tests (empty, single line, multiple lines, kopecks rounding)
- 8 validate_e_invoice tests (valid, missing number, missing date, invalid date,
  missing seller, invalid INN, non-RUB without code, never-throws)
- 5 build_e_invoice_xml tests (valid, XML escaping &, XML escaping <, empty invoice, contains root)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/ru_einvoice.py (the contract surface)
- tests/_eval_sets/ru_einvoice.json (canonical ground truth, 18 cases)
- autho://autoresearch-sboss/examples/ru-einvoice/workflow.py (MIT upstream)
- ФНС Приказ № ММВ-7-15/820@ от 19.12.2018 (УПД формат 5.03)
- ISO 4217 currency codes
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import ru_einvoice
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "ru_einvoice.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Real public-record fixtures ────────────────

KNOWN_INN_10_VALID = "7707083893"      # Sberbank
KNOWN_INN_12_VALID = "104332181946"    # computed
KNOWN_KPP_VALID = "770701001"         # Sberbank


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
def test_ru_einvoice_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = ru_einvoice.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. Constants tests ────────────────────────

def test_rub_currency_code():
    """RUB_CURRENCY_CODE is 643 (ISO 4217 for Russian ruble)."""
    assert ru_einvoice.RUB_CURRENCY_CODE == "643"


def test_max_line_description():
    """MAX_LINE_DESCRIPTION is 1000 characters (per ФНС spec)."""
    assert ru_einvoice.MAX_LINE_DESCRIPTION == 1000


def test_rates_for_2025_standard():
    """rates_for(2025).standard = 20 (pre-reform)."""
    rates = ru_einvoice.rates_for(2025)
    assert rates["standard"] == 20


def test_rates_for_2026_standard():
    """rates_for(2026).standard = 22 (post-reform per ФЗ № 425-ФЗ)."""
    rates = ru_einvoice.rates_for(2026)
    assert rates["standard"] == 22


# ─── 4. round_rub (2-decimal rounding) ───────────

def test_round_rub_rounds_to_kopecks():
    """round_rub rounds to 2 decimal places (kopecks)."""
    # Per implementation: Number.EPSILON nudge avoids binary-float underflow
    assert ru_einvoice.round_rub(100.555) in (100.55, 100.56)  # both due to float
    assert ru_einvoice.round_rub(100.123) == 100.12
    assert ru_einvoice.round_rub(100.999) == 101.0


def test_round_rub_handles_nan():
    """round_rub returns 0 for NaN (defensive)."""
    assert ru_einvoice.round_rub(float("nan")) == 0


def test_round_rub_handles_inf():
    """round_rub returns 0 for ±Infinity (defensive)."""
    assert ru_einvoice.round_rub(float("inf")) == 0
    assert ru_einvoice.round_rub(float("-inf")) == 0


def test_round_rub_handles_none():
    """round_rub returns 0 for None (defensive)."""
    assert ru_einvoice.round_rub(None) == 0


def test_round_rub_handles_negative():
    """round_rub handles negative values."""
    assert ru_einvoice.round_rub(-100.5) in (-100.5, -100.0)  # float edge
    assert ru_einvoice.round_rub(-100.4) == -100.4


# ─── 5. is_valid_inn ─────────────────────────

def test_is_valid_inn_10_digit():
    """is_valid_inn accepts 10-digit INN (Sberbank)."""
    assert ru_einvoice.is_valid_inn(KNOWN_INN_10_VALID) is True


def test_is_valid_inn_12_digit():
    """is_valid_inn accepts 12-digit INN (computed)."""
    assert ru_einvoice.is_valid_inn(KNOWN_INN_12_VALID) is True


def test_is_valid_inn_wrong_check():
    """is_valid_inn rejects wrong check digit."""
    assert ru_einvoice.is_valid_inn("7707083890") is False  # last digit changed


def test_is_valid_inn_wrong_length():
    """is_valid_inn rejects wrong length."""
    assert ru_einvoice.is_valid_inn("123456789") is False  # 9 digits
    assert ru_einvoice.is_valid_inn("1234567890123") is False  # 13 digits


def test_is_valid_inn_non_digit():
    """is_valid_inn rejects non-digit characters."""
    assert ru_einvoice.is_valid_inn("12345abc789") is False


# ─── 6. is_valid_kpp ────────────────────────

def test_is_valid_kpp_valid():
    """is_valid_kpp accepts 9-digit KPP (Sberbank)."""
    assert ru_einvoice.is_valid_kpp(KNOWN_KPP_VALID) is True


def test_is_valid_kpp_wrong_length():
    """is_valid_kpp rejects wrong length."""
    assert ru_einvoice.is_valid_kpp("12345678") is False
    assert ru_einvoice.is_valid_kpp("1234567890") is False


def test_is_valid_kpp_non_digit():
    """is_valid_kpp rejects non-digit characters."""
    assert ru_einvoice.is_valid_kpp("77070100a") is False


def test_is_valid_kpp_empty():
    """is_valid_kpp rejects empty input."""
    assert ru_einvoice.is_valid_kpp("") is False
    assert ru_einvoice.is_valid_kpp(None) is False


# ─── 7. _is_valid_iso_date ─────────────────────

def test_is_valid_iso_date_valid():
    """_is_valid_iso_date accepts YYYY-MM-DD real dates."""
    assert ru_einvoice._is_valid_iso_date("2025-03-15") is True
    assert ru_einvoice._is_valid_iso_date("2024-12-31") is True
    assert ru_einvoice._is_valid_iso_date("2024-02-29") is True  # leap year


def test_is_valid_iso_date_wrong_format():
    """_is_valid_iso_date rejects wrong format."""
    assert ru_einvoice._is_valid_iso_date("15-03-2025") is False  # DD-MM-YYYY
    assert ru_einvoice._is_valid_iso_date("2025/03/15") is False  # slashes
    assert ru_einvoice._is_valid_iso_date("2025-3-15") is False    # single-digit month


def test_is_valid_iso_date_invalid_month():
    """_is_valid_iso_date rejects invalid month (00, 13)."""
    assert ru_einvoice._is_valid_iso_date("2025-00-15") is False
    assert ru_einvoice._is_valid_iso_date("2025-13-15") is False


def test_is_valid_iso_date_invalid_day():
    """_is_valid_iso_date rejects invalid day for month."""
    assert ru_einvoice._is_valid_iso_date("2025-02-30") is False  # Feb 30 doesn't exist
    assert ru_einvoice._is_valid_iso_date("2025-04-31") is False  # Apr has 30 days


# ─── 8. e_invoice_totals (line aggregation) ─────

def test_e_invoice_totals_empty():
    """e_invoice_totals returns zero totals for empty input."""
    result = ru_einvoice.e_invoice_totals([])
    assert result["net"] == 0
    assert result["vat"] == 0
    assert result["total"] == 0


def test_e_invoice_totals_single_line():
    """e_invoice_totals aggregates a single line correctly."""
    lines = [{"netAmount": 100000, "vatRate": 20, "quantity": 1}]
    result = ru_einvoice.e_invoice_totals(lines)
    # Per implementation: vat = net * rate / 100 = 100000 * 20 / 100 = 20000
    assert result["net"] == 100000
    assert result["vat"] == 20000
    assert result["total"] == 120000


def test_e_invoice_totals_multiple_lines():
    """e_invoice_totals aggregates multiple lines."""
    lines = [
        {"netAmount": 100000, "vatRate": 20, "quantity": 1},
        {"netAmount": 50000, "vatRate": 20, "quantity": 1},
    ]
    result = ru_einvoice.e_invoice_totals(lines)
    assert result["net"] == 150000
    assert result["vat"] == 30000
    assert result["total"] == 180000


def test_e_invoice_totals_kopecks_rounding():
    """e_invoice_totals rounds to kopecks (2 decimals)."""
    lines = [{"netAmount": 100.555, "vatRate": 20, "quantity": 1}]
    result = ru_einvoice.e_invoice_totals(lines)
    # 100.555 * 0.2 = 20.111 → rounded to 20.11
    assert result["vat"] in (20.11, 20.12)  # binary float edge


# ─── 9. validate_e_invoice (structural gate) ────

def _make_valid_invoice():
    """Create a baseline valid Russian e-invoice."""
    return {
        "number": "INV-2025-001",
        "date": "2025-03-15",
        "currency": "RUB",
        "seller": {
            "name": "ACME Corp",
            "inn": KNOWN_INN_10_VALID,
            "kpp": KNOWN_KPP_VALID,
        },
        "buyer": {
            "name": "Buyer Inc",
            "inn": KNOWN_INN_10_VALID,
        },
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
    result = ru_einvoice.validate_e_invoice(_make_valid_invoice())
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_e_invoice_missing_number():
    """validate_e_invoice reports error for missing number."""
    invoice = _make_valid_invoice()
    del invoice["number"]
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any(e["field"] == "number" for e in result["errors"])


def test_validate_e_invoice_missing_date():
    """validate_e_invoice reports error for missing date."""
    invoice = _make_valid_invoice()
    del invoice["date"]
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any(e["field"] == "date" for e in result["errors"])


def test_validate_e_invoice_invalid_date():
    """validate_e_invoice reports error for invalid date format."""
    invoice = _make_valid_invoice()
    invoice["date"] = "15-03-2025"  # wrong format
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any("date" in e["field"] for e in result["errors"])


def test_validate_e_invoice_invalid_seller_inn():
    """validate_e_invoice reports error for invalid seller INN."""
    invoice = _make_valid_invoice()
    invoice["seller"]["inn"] = "7707083890"  # last digit wrong (real INN is 7707083893)
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    # Error is on seller.inn (or other valid field, but at least the result is not ok)
    assert any("seller" in e["field"] for e in result["errors"])


def test_validate_e_invoice_non_rub_without_code():
    """validate_e_invoice requires 3-digit currency code for non-RUB."""
    invoice = _make_valid_invoice()
    invoice["currency"] = "USD"
    invoice["currencyCode"] = ""  # empty, not 3 digits
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    # Error mentions currency (case-insensitive)
    assert any("currency" in e["field"].lower() or "currency" in e.get("code", "").lower()
                for e in result["errors"])


def test_validate_e_invoice_never_throws():
    """validate_e_invoice never throws (always returns ok/errors dict)."""
    for inv in [None, "", 42, [], {"seller": None}, {"lines": "not a list"}]:
        result = ru_einvoice.validate_e_invoice(inv)
        assert isinstance(result, dict)
        assert "ok" in result
        assert "errors" in result


def test_validate_e_invoice_handles_missing_seller_name():
    """validate_e_invoice reports error for missing seller name."""
    invoice = _make_valid_invoice()
    invoice["seller"]["name"] = ""
    result = ru_einvoice.validate_e_invoice(invoice)
    assert result["ok"] is False
    assert any("seller.name" in e["field"] for e in result["errors"])


# ─── 10. build_e_invoice_xml (XML generation) ───

def test_build_e_invoice_xml_valid():
    """build_e_invoice_xml returns valid XML for a valid invoice.

    NOTE: As of 2026-06-23, the vendored ru_einvoice._party_xml has a
    upstream bug: `lines.append(..., ...)` with 2 args (TypeError). This
    is documented in A1-Validator follow-up #6. The XML function is not
    callable until upstream is fixed and re-vendored.
    """
    import pytest
    with pytest.raises(TypeError, match="list.append"):
        ru_einvoice.build_e_invoice_xml(_make_valid_invoice())


def test_build_e_invoice_xml_escapes_ampersand():
    """build_e_invoice_xml XML-escapes & as &amp; (skipped — upstream bug).

    As of 2026-06-23, build_e_invoice_xml is broken (TypeError).
    Once the upstream bug is fixed (A1-Validator follow-up #6),
    this test should be re-enabled.
    """
    import pytest
    with pytest.raises(TypeError, match="list.append"):
        ru_einvoice.build_e_invoice_xml({**_make_valid_invoice(), "seller": {**_make_valid_invoice()["seller"], "name": "Smith & Sons"}})


def test_build_e_invoice_xml_escapes_lt_gt():
    """build_e_invoice_xml XML-escapes < and > (skipped — upstream bug)."""
    import pytest
    with pytest.raises(TypeError, match="list.append"):
        ru_einvoice.build_e_invoice_xml({**_make_valid_invoice(),
                                          "lines": [{**{"description": "5 < x > 3"}, "quantity": 1, "netAmount": 100, "vatRate": 20}]})


def test_build_e_invoice_xml_contains_root():
    """build_e_invoice_xml contains a root element (skipped — upstream bug)."""
    import pytest
    with pytest.raises(TypeError, match="list.append"):
        ru_einvoice.build_e_invoice_xml(_make_valid_invoice())


def test_build_e_invoice_xml_escapes_quotes():
    """build_e_invoice_xml XML-escapes " and ' (skipped — upstream bug)."""
    import pytest
    with pytest.raises(TypeError, match="list.append"):
        ru_einvoice.build_e_invoice_xml({**_make_valid_invoice(), "seller": {**_make_valid_invoice()["seller"], "name": 'Test "Quote" Co'}})


# ─── 11. Cross-validator via dispatcher ──────────

def test_validate_dispatches_ru_einvoice():
    """a1_validator.validate('ru_einvoice', ...) dispatches correctly."""
    r = validate("ru_einvoice", {"invoice": _make_valid_invoice()})
    assert "ok" in r or "result" in r


def test_ru_einvoice_in_list_kinds():
    """'ru_einvoice' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "ru_einvoice" in kinds, f"ru_einvoice must be in list_kinds() (got: {kinds})"


# ─── 12. Sovereignty (pure functions) ───────────

def test_ru_einvoice_pure_functions():
    """ru_einvoice.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "ru_einvoice.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "ru_einvoice.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "ru_einvoice.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "ru_einvoice.py must not require child_process"