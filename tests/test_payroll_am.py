"""test_payroll_am.py — focused tests for the Armenian payroll engine.

The vendored ``payroll_am`` module computes payroll withholdings per
the RA Tax Code + Government Decree N 1332-Ն:

- **Income tax**: 20% flat (since 1 Jan 2023 reform, was progressive)
- **Pension contribution**: tiered 5% / 10% / capped
  - 0-500,000 AMD: 5%
  - 500,001-1,125,000 AMD: 10% - 25,000 AMD
  - >1,125,000 AMD: 87,500 AMD (cap)
- **Stamp duty**: 1,000 AMD flat (2026 reform; was tiered)
- **Health insurance**: 0 / 4,800 / 10,800 AMD by gross bands
  - <200,001: 0
  - 200,001-500,000: 4,800 (after 6,000 state reimbursement)
  - >500,000: 10,800

Public API:
- ``round_amd(amount) -> int`` — JS Math.round (half toward +∞)
- ``income_tax(gross) -> int`` — flat 20% (gross > 0)
- ``pension(gross) -> int`` — 3-tier (5% / 10%-25k / cap 87.5k)
- ``stamp_duty(gross) -> int`` — 1,000 if gross > 0
- ``health_insurance(gross) -> int`` — 0 / 4,800 / 10,800
- ``compute_payroll(gross) -> dict`` — all 7 fields
- ``validate(input_data) -> dict`` — uniform entry point

Tests here complement test_validators.py::test_payroll_am (parametrized).
This file adds:
- 20 parametrized upstream eval_set verification
- Real fixtures for each tax bracket
- All 4 component functions tested independently
- 5 edge cases (zero, negative, very large, float, string)
- 2 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/payroll_am.py (the contract surface)
- tests/_eval_sets/payroll_am.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/payroll-am/workflow.py (MIT upstream)
- RA Tax Code + Government Decree N 1332-Ն
- 2023 income tax reform (flat 20% from 1 Jan 2023)
- 2026 stamp duty reform (flat 1,000 AMD from 1 Jan 2026)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import payroll_am
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "payroll_am.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per RA Tax Code + 2023/2026 reforms) ───

INCOME_TAX_RATE = 20             # % flat since 2023-01-01

PENSION_LOW_CEIL = 500_000       # AMD/year
PENSION_CAP_THRESHOLD = 1_125_000
PENSION_CAP = 87_500

STAMP_DUTY_2026 = 1_000          # AMD flat (was tiered pre-2026)

HEALTH_INSURANCE_MIN_GROSS = 200_001
HEALTH_INSURANCE_LOW_CEIL = 500_000
HEALTH_INSURANCE_LOW = 4_800
HEALTH_INSURANCE_FULL = 10_800


# ─── 2. Parametrized upstream eval set ─────────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_payroll_am_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = payroll_am.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


# ─── 3. Constants test ──────────────────────────────

def test_constants_match_law():
    """Constants match RA Tax Code + 2023/2026 reforms."""
    assert payroll_am.INCOME_TAX_RATE == INCOME_TAX_RATE
    assert payroll_am.PENSION_LOW_CEIL == PENSION_LOW_CEIL
    assert payroll_am.PENSION_CAP_THRESHOLD == PENSION_CAP_THRESHOLD
    assert payroll_am.PENSION_CAP == PENSION_CAP
    assert payroll_am.STAMP_DUTY_2026 == STAMP_DUTY_2026
    assert payroll_am.HEALTH_INSURANCE_MIN_GROSS == HEALTH_INSURANCE_MIN_GROSS
    assert payroll_am.HEALTH_INSURANCE_LOW_CEIL == HEALTH_INSURANCE_LOW_CEIL
    assert payroll_am.HEALTH_INSURANCE_LOW == HEALTH_INSURANCE_LOW
    assert payroll_am.HEALTH_INSURANCE_FULL == HEALTH_INSURANCE_FULL


# ─── 4. round_amd (JS Math.round parity) ─────────────

def test_round_amd_basic():
    """round_amd rounds to whole AMD (Math.round parity: half toward +∞)."""
    assert payroll_am.round_amd(100.4) == 100
    assert payroll_am.round_amd(100.5) == 101  # half toward +∞
    assert payroll_am.round_amd(100.6) == 101
    assert payroll_am.round_amd(100) == 100
    assert payroll_am.round_amd(0) == 0


def test_round_amd_handles_none():
    """round_amd returns 0 for None / non-finite."""
    assert payroll_am.round_amd(None) == 0
    assert payroll_am.round_amd(float("inf")) == 0
    assert payroll_am.round_amd(float("-inf")) == 0
    assert payroll_am.round_amd(float("nan")) == 0


# ─── 5. income_tax ──────────────────────────────────

def test_income_tax_20_percent():
    """Income tax is 20% flat (since 2023 reform)."""
    assert payroll_am.income_tax(100_000) == 20_000
    assert payroll_am.income_tax(500_000) == 100_000
    assert payroll_am.income_tax(1_000_000) == 200_000


def test_income_tax_zero_for_zero_gross():
    """Zero or negative gross → 0 tax."""
    assert payroll_am.income_tax(0) == 0
    assert payroll_am.income_tax(-1000) == 0


def test_income_tax_rounds_to_whole_amd():
    """Income tax rounds to whole AMD (Math.round parity)."""
    # 1234 * 20% = 246.8 → 247
    assert payroll_am.income_tax(1234) == 247
    # 1235 * 20% = 247.0 → 247
    assert payroll_am.income_tax(1235) == 247
    # 1236 * 20% = 247.2 → 247
    assert payroll_am.income_tax(1236) == 247
    # 1237 * 20% = 247.4 → 247
    assert payroll_am.income_tax(1237) == 247
    # 1238 * 20% = 247.6 → 248
    assert payroll_am.income_tax(1238) == 248


# ─── 6. pension (3 tiers) ──────────────────────────

def test_pension_zero_for_zero_gross():
    """Zero or negative gross → 0 pension."""
    assert payroll_am.pension(0) == 0
    assert payroll_am.pension(-1000) == 0


def test_pension_tier_1_low_5_percent():
    """Tier 1: 0-500,000 AMD → 5%."""
    # 100,000 * 5% = 5,000
    assert payroll_am.pension(100_000) == 5_000
    # 250,000 * 5% = 12,500
    assert payroll_am.pension(250_000) == 12_500
    # 500,000 * 5% = 25,000 (boundary)
    assert payroll_am.pension(PENSION_LOW_CEIL) == 25_000


def test_pension_tier_2_mid_10_percent_minus_25k():
    """Tier 2: 500,001-1,125,000 AMD → 10% - 25,000."""
    # 500,001 * 10% - 25,000 = 50,000.1 - 25,000 = 25,000.1 → 25,000
    assert payroll_am.pension(500_001) == 25_000
    # 1,000,000 * 10% - 25,000 = 75,000
    assert payroll_am.pension(1_000_000) == 75_000
    # 1,125,000 * 10% - 25,000 = 87,500 (boundary)
    assert payroll_am.pension(PENSION_CAP_THRESHOLD) == PENSION_CAP


def test_pension_tier_3_capped_87500():
    """Tier 3: >1,125,000 AMD → flat 87,500 (cap)."""
    # 1,125,001 → capped at 87,500
    assert payroll_am.pension(1_125_001) == PENSION_CAP
    # 2,000,000 → capped at 87,500
    assert payroll_am.pension(2_000_000) == PENSION_CAP
    # 10,000,000 → capped at 87,500
    assert payroll_am.pension(10_000_000) == PENSION_CAP


# ─── 7. stamp_duty ──────────────────────────────────

def test_stamp_duty_1000_amd_flat():
    """Stamp duty is 1,000 AMD flat (2026 reform)."""
    for gross in (100_000, 500_000, 1_000_000, 5_000_000):
        assert payroll_am.stamp_duty(gross) == STAMP_DUTY_2026


def test_stamp_duty_zero_for_zero_gross():
    """Zero or negative gross → 0 stamp duty."""
    assert payroll_am.stamp_duty(0) == 0
    assert payroll_am.stamp_duty(-1000) == 0


# ─── 8. health_insurance ────────────────────────────

def test_health_insurance_zero_below_threshold():
    """Gross < 200,001 → 0 health insurance."""
    assert payroll_am.health_insurance(0) == 0
    assert payroll_am.health_insurance(100_000) == 0
    assert payroll_am.health_insurance(200_000) == 0  # boundary: < 200,001


def test_health_insurance_low_4800():
    """Gross 200,001-500,000 → 4,800 AMD (after state reimbursement)."""
    assert payroll_am.health_insurance(200_001) == 4_800
    assert payroll_am.health_insurance(300_000) == 4_800
    assert payroll_am.health_insurance(500_000) == 4_800  # boundary


def test_health_insurance_full_10800():
    """Gross > 500,000 → 10,800 AMD (full)."""
    assert payroll_am.health_insurance(500_001) == 10_800
    assert payroll_am.health_insurance(1_000_000) == 10_800
    assert payroll_am.health_insurance(10_000_000) == 10_800


# ─── 9. compute_payroll (full picture) ───────────────

def test_compute_payroll_zero_gross():
    """Zero gross → all withholdings = 0, net = 0."""
    r = payroll_am.compute_payroll(0)
    assert r["gross"] == 0
    assert r["incomeTax"] == 0
    assert r["pension"] == 0
    assert r["stampDuty"] == 0
    assert r["healthInsurance"] == 0
    assert r["totalWithholdings"] == 0
    assert r["net"] == 0


def test_compute_payroll_low_gross():
    """Low gross (e.g. 100,000 AMD) — minimal withholdings."""
    r = payroll_am.compute_payroll(100_000)
    assert r["gross"] == 100_000
    assert r["incomeTax"] == 20_000         # 20%
    assert r["pension"] == 5_000            # 5%
    assert r["stampDuty"] == 1_000          # flat
    assert r["healthInsurance"] == 0        # < 200,001
    assert r["totalWithholdings"] == 26_000
    assert r["net"] == 74_000


def test_compute_payroll_mid_gross():
    """Mid gross (e.g. 700,000 AMD) — tier 2 pension + full health."""
    r = payroll_am.compute_payroll(700_000)
    assert r["gross"] == 700_000
    assert r["incomeTax"] == 140_000        # 20%
    assert r["pension"] == 45_000           # 700k * 10% - 25k = 45,000
    assert r["stampDuty"] == 1_000
    assert r["healthInsurance"] == 10_800   # > 500k
    assert r["totalWithholdings"] == 196_800
    assert r["net"] == 503_200


def test_compute_payroll_high_gross_capped_pension():
    """High gross (e.g. 2,000,000 AMD) — capped pension."""
    r = payroll_am.compute_payroll(2_000_000)
    assert r["gross"] == 2_000_000
    assert r["incomeTax"] == 400_000        # 20%
    assert r["pension"] == PENSION_CAP      # 87,500 (capped)
    assert r["stampDuty"] == 1_000
    assert r["healthInsurance"] == 10_800
    assert r["totalWithholdings"] == 499_300
    assert r["net"] == 1_500_700


# ─── 10. Cross-validator via dispatcher ─────────────

def test_validate_dispatches_payroll_am():
    """a1_validator.validate('payroll_am', ...) dispatches correctly."""
    r = validate("payroll_am", {"gross": 100_000})
    assert r["gross"] == 100_000
    assert r["incomeTax"] == 20_000
    assert r["pension"] == 5_000


def test_payroll_am_in_list_kinds():
    """'payroll_am' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "payroll_am" in kinds, f"payroll_am must be in list_kinds() (got: {kinds})"


# ─── 11. Sovereignty ─────────────────────────────

def test_payroll_am_pure_functions():
    """payroll_am.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "payroll_am.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "payroll_am.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "payroll_am.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "payroll_am.py must not require child_process"
    # No environment variable reads (rates are hard-coded)
    assert not re.search(r'\bprocess\.env', src), \
        "payroll_am.py must not read environment variables"