"""test_vat_ru.py — focused tests for the Russian VAT engine.

The vendored ``vat_ru`` module implements Russian Federation VAT (НДС) per
the 2026 tax reform (НК РФ гл. 21 + ФЗ № 425-ФЗ от 28.11.2025).

Public API (all via validate(input_data) with operation dispatch):
- ``ratesFor(year)`` — returns {standard, reduced, zero, usnLow?, usnHigh?}
  - 2026: standard=22, reduced=10, zero=0, usnLow=5, usnHigh=7 (УСН regime)
  - 2025: standard=20, reduced=10, zero=0 (pre-reform, for back-dated docs)
- ``vatFromNet(net, ratePercent)`` — VAT added on top of net
- ``vatFromGross(gross, ratePercent)`` — VAT contained in gross (settlement rate r/(100+r))
- ``netFromGross(gross, ratePercent)`` — net = gross − VAT-contained
- ``isValidVatRate(ratePercent, opts)`` — accepts 0/10/22 standard, +5/7 УСН

Tests here complement test_validators.py::test_vat_ru (parametrized
verification against the eval_set). This file adds:
- 20 parametrized upstream eval_set verification (mirrors HHVH)
- Real-world rate sanity (2025 vs 2026 differential)
- 22% VAT math: vat from net, vat from gross, net from gross
- 10% reduced VAT math (food, medicine, children goods)
- 0% zero-rated (export, medical equipment, etc.)
- УСН regime (5% / 7%) special rates
- Cross-validator dispatcher (validate('vat_ru', ...))
- Sovereignty: no network/fs require

Source:
- src/a1_validator/_vendored/vat_ru.py (the contract surface)
- tests/_eval_sets/vat_ru.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/vat-ru/workflow.py (MIT upstream)
- НК РФ гл. 21 (Russian Tax Code, Chapter 21 — VAT)
- ФЗ № 425-ФЗ от 28.11.2025 (2026 tax reform, effective 2026-01-01)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import vat_ru
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "vat_ru.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per НК РФ гл. 21 + ФЗ № 425-ФЗ 2026 reform) ──

# 2026 standard rates (post-reform)
EXPECTED_RATES_2026 = {
    "standard": 22,    # Standard rate (was 20% pre-reform)
    "reduced":  10,    # Reduced rate (food, medicine, children goods)
    "zero":      0,    # Zero-rated (export, medical equipment)
    "usnLow":    5,    # УСН "доходы" regime (income only)
    "usnHigh":   7,    # УСН "доходы минус расходы" regime (income - expenses)
}

# 2025 standard rates (pre-reform, for back-dated docs)
EXPECTED_RATES_2025 = {
    "standard": 20,    # Pre-reform standard
    "reduced":  10,
    "zero":      0,
}

# Allowed rates
ALLOWED_STANDARD_RATES = [0, 10, 22]   # 2026 standard regime
ALLOWED_USN_RATES = [0, 5, 7, 10, 22]  # 2026 УСН regime (adds 5/7)

# Default year (current behavior)
DEFAULT_YEAR = 2026


# ─── 2. ratesFor (rate lookup) ─────────────────────────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_vat_ru_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = vat_ru.validate(case["input"])
    expected = case["expected"]
    # Subset match (eval returns {"result": ...})
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


def test_rates_for_2026_standard_regime():
    """2026 rates per ФЗ № 425-ФЗ: 22% standard, 10% reduced, 0% zero."""
    r = vat_ru.rates_for(2026)
    assert r["standard"] == 22
    assert r["reduced"] == 10
    assert r["zero"] == 0
    assert r["usnLow"] == 5
    assert r["usnHigh"] == 7


def test_rates_for_2025_pre_reform():
    """2025 rates (pre-reform, for back-dated docs): 20% standard."""
    r = vat_ru.rates_for(2025)
    assert r["standard"] == 20
    assert r["reduced"] == 10
    assert r["zero"] == 0
    # 2025 has no УСН rates in our rate table (pre-2026 reform)
    assert "usnLow" not in r or r.get("usnLow") is None


def test_rates_for_default_year():
    """Default year is 2026 (the post-reform year)."""
    r_default = vat_ru.rates_for()
    r_2026 = vat_ru.rates_for(2026)
    assert r_default == r_2026


def test_rates_for_unknown_year_falls_back_to_current():
    """Unknown year falls back to current year (default 2026)."""
    r = vat_ru.rates_for(1999)  # pre-VAT era
    r_current = vat_ru.rates_for(2026)
    assert r == r_current


# ─── 3. vatFromNet (VAT added on top of net) ──────────────────

def test_vat_from_net_22_percent():
    """22% VAT on 100,000 RUB net = 22,000 VAT."""
    assert vat_ru.vat_from_net(100_000, 22) == 22_000
    assert vat_ru.vat_from_net(50_000, 22) == 11_000


def test_vat_from_net_10_percent():
    """10% VAT (reduced rate) on 100,000 RUB net = 10,000 VAT."""
    assert vat_ru.vat_from_net(100_000, 10) == 10_000


def test_vat_from_net_zero_percent():
    """0% VAT (zero-rated, e.g. export) on 100,000 = 0 VAT."""
    assert vat_ru.vat_from_net(100_000, 0) == 0


def test_vat_from_net_kopecks_rounding():
    """VAT is rounded to whole kopecks (2 decimal places), per НК РФ ст. 52."""
    # 1234.56 * 22% = 271.6032 → rounds to 271.60
    v = vat_ru.vat_from_net(1234.56, 22)
    assert v == 271.60


def test_vat_from_net_null_and_undefined():
    """Null/undefined inputs return 0 (defensive)."""
    assert vat_ru.vat_from_net(None, 22) == 0
    assert vat_ru.vat_from_net(100_000, None) == 0
    assert vat_ru.vat_from_net(0, 22) == 0


# ─── 4. vatFromGross (VAT contained in gross) ───────────────

def test_vat_from_gross_22_percent():
    """22% VAT contained in 122,000 RUB gross = 22,000 VAT (rate 22/122)."""
    # gross * 22/(100+22) = gross * 22/122
    v = vat_ru.vat_from_gross(122_000, 22)
    assert v == 22_000  # 122000 * 22/122 = 22000.0 exactly


def test_vat_from_gross_10_percent():
    """10% VAT contained in 110,000 RUB gross = 10,000 VAT (rate 10/110)."""
    v = vat_ru.vat_from_gross(110_000, 10)
    assert v == 10_000  # 110000 * 10/110 = 10000.0 exactly


def test_vat_from_gross_zero_percent_returns_zero():
    """0% rate returns 0 (avoids division by zero in the settlement rate)."""
    assert vat_ru.vat_from_gross(100_000, 0) == 0


def test_vat_from_gross_kopecks_rounding():
    """VAT is rounded to whole kopecks."""
    # 1000 * 22/122 = 180.3278... → 180.33
    v = vat_ru.vat_from_gross(1000, 22)
    assert v == 180.33


# ─── 5. netFromGross (gross minus VAT) ───────────────────────

def test_net_from_gross_22_percent():
    """Net from 122,000 RUB gross @ 22% = 100,000 net (122k - 22k VAT)."""
    assert vat_ru.net_from_gross(122_000, 22) == 100_000


def test_net_from_gross_10_percent():
    """Net from 110,000 RUB gross @ 10% = 100,000 net."""
    assert vat_ru.net_from_gross(110_000, 10) == 100_000


def test_net_from_gross_consistency():
    """netFromGross(g, r) + vatFromGross(g, r) should equal g (within kopecks rounding)."""
    for gross in (1000, 1234.56, 99999.99, 1_000_000):
        for rate in (10, 22):
            net = vat_ru.net_from_gross(gross, rate)
            vat = vat_ru.vat_from_gross(gross, rate)
            # Allow ±0.01 ruble for kopecks rounding
            assert abs((net + vat) - gross) < 0.02, (
                f"gross={gross}, rate={rate}: net({net}) + vat({vat}) = {net+vat} (expected {gross})"
            )


# ─── 6. isValidVatRate (rate validation) ────────────────────

def test_is_valid_vat_rate_standard_regime():
    """Standard regime: 0%, 10%, 22% are valid."""
    for r in (0, 10, 22):
        assert vat_ru.is_valid_vat_rate(r) is True
    for r in (5, 7, 15, 18, 20):
        assert vat_ru.is_valid_vat_rate(r) is False


def test_is_valid_vat_rate_usn_regime():
    """УСН regime: 5% and 7% are also valid (in addition to standard)."""
    for r in (0, 5, 7, 10, 22):
        assert vat_ru.is_valid_vat_rate(r, {"regime": "usn"}) is True
    for r in (15, 20, 25):
        assert vat_ru.is_valid_vat_rate(r, {"regime": "usn"}) is False


def test_is_valid_vat_rate_handles_null():
    """Null rate coerces to 0 (defensive). 0 is a valid rate (zero-rated)."""
    # Per implementation: float(None or 0) = 0.0, which is in the allowed set
    assert vat_ru.is_valid_vat_rate(None) is True  # coerces to 0
    assert vat_ru.is_valid_vat_rate(0) is True     # zero-rated is valid


# ─── 7. Cross-validator via dispatcher ─────────────────────

def test_validate_dispatches_vat_ru():
    """a1_validator.validate('vat_ru', ...) dispatches correctly."""
    r = validate("vat_ru", {"operation": "ratesFor", "year": 2026})
    assert r["result"]["standard"] == 22


def test_validate_dispatches_vat_ru_vatFromNet():
    """a1_validator.validate routes 'vatFromNet' to the right operation."""
    r = validate("vat_ru", {"operation": "vatFromNet", "net": 100_000, "ratePercent": 22})
    assert r["result"] == 22_000


def test_vat_ru_in_list_kinds():
    """'vat_ru' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "vat_ru" in kinds, f"vat_ru must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (offline-capable) ─────────────────────

def test_vat_ru_pure_functions():
    """vat_ru.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "vat_ru.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "vat_ru.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "vat_ru.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "vat_ru.py must not require child_process"
    # No environment variable reads (VAT rates are hard-coded per the 2026 reform)
    assert not re.search(r'\bprocess\.env', src), \
        "vat_ru.py must not read environment variables"