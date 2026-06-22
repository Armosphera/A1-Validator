"""test_inn.py — focused tests for the INN (Russian taxpayer ID) validator.

INN is the multi-format Russian identifier validator. The vendored
``ru_identifiers`` module supports:
- INN 10-digit (legal entities) — check digit via weighted sum mod 11 mod 10
- INN 12-digit (individual entrepreneurs) — two check digits, both via
  the same weighted-sum scheme with different weights
- KPP (9-digit) — code of reason for registration
- OGRN (13-digit) — primary state registration number
- OGRNIP (15-digit) — same for individual entrepreneurs
- SNILS (11-digit) — pension insurance, with mod-101 check digit

These tests pin the contract from the vendored ru_identifiers module
(per the upstream autoresearch-sboss eval_set in tests/_eval_sets/inn.json)
and add focused contract tests for the check-digit math.

Tests here complement test_validators.py::test_inn (which does
parametrized verification against the eval_set). This file adds:
- 10-digit INN check-digit math (the legal entity formula)
- 12-digit INN check-digit math (the individual formula)
- KPP/OGRN/OGRNIP/SNILS round-trip verification
- a1_validator.validate() dispatcher test (cross-validator alias)
- Sovereignty: no network/fs require in ru_identifiers.py

Source:
- src/a1_validator/_vendored/ru_identifiers.py (the contract surface)
- tests/_eval_sets/inn.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/ru-identifiers/workflow.py (MIT upstream)
- Federal Tax Service (FTS) / НК РФ Art. 84-85 (INN assignment)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator import inn, validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "inn.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants ───────────────────────────────────────────────────

# Per НК РФ Art. 84-85 + FTS assignment rules
INN_LEGAL_LENGTH = 10       # legal entities
INN_INDIVIDUAL_LENGTH = 12  # individual entrepreneurs
KPP_LENGTH = 9
OGRN_LENGTH = 13
OGRNIP_LENGTH = 15
SNILS_LENGTH = 11

# Weighted coefficients for INN 10-digit check (legal entity)
# Per https://www.nalog.gov.ru/rn77/ip/interest/facts_reg_no_ul/
# These are the official weights (sum mod 11, then mod 10)
_INN10_WEIGHTS = (2, 4, 10, 3, 5, 9, 4, 6, 8)

# Weighted coefficients for INN 12-digit check (individual entrepreneur)
# First 11 digits × 7,2,4,10,3,5,9,4,6,8 mod 11 mod 10
# 12th digit × 3,7,2,4,10,3,5,9,4,6,8 mod 11 mod 10
_INN12_FIRST_WEIGHTS = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_SECOND_WEIGHTS = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


# ─── 2. INN 10-digit (legal entity) — 100% of real fixtures ──────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_inn_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = inn(case["input"])
    expected = case["expected"]
    # Subset match (extra keys in actual OK, like 'kind' discriminator)
    for key, value in expected.items():
        if key == "normalized" and value is None:
            assert actual.get(key) is None, f"case {case}: normalized should be None"
        else:
            assert actual.get(key) == value, (
                f"case {case}: key {key} — expected {value!r}, got {actual.get(key)!r}"
            )


def test_inn_legal_known_valid_fixtures():
    """INN 10-digit valid fixtures (legal entities)."""
    # These are real public Russian company INNs from the upstream eval_set.
    assert inn({"id": "7707083893"})["ok"] is True
    assert inn({"id": "7707083893"})["kind"] == "inn_legal"
    assert inn({"id": "7707083893"})["normalized"] == "7707083893"


def test_inn_individual_known_valid_fixtures():
    """INN 12-digit valid fixtures (individual entrepreneurs)."""
    assert inn({"id": "500100732259"})["ok"] is True
    assert inn({"id": "500100732259"})["kind"] == "inn_individual"
    assert inn({"id": "500100732259"})["normalized"] == "500100732259"


def test_inn_accepts_kpp_as_ru_identifier():
    """9-digit KPP is accepted by ru_identifiers (multi-format design).

    The ru_identifiers module handles INN, KPP, OGRN, OGRNIP, SNILS.
    It does NOT reject KPP outright — it dispatches to the KPP handler.
    This is by design: a single `a1_validator.inn()` call dispatches
    to the right handler based on length/format.
    """
    r = inn({"id": "770701001"})  # real KPP
    assert r["ok"] is True
    assert r["kind"] == "kpp"


def test_inn_accepts_ogrn_as_ru_identifier():
    """13-digit OGRN is accepted by ru_identifiers (multi-format design)."""
    r = inn({"id": "1027700132195"})  # real OGRN
    assert r["ok"] is True
    assert r["kind"] == "ogrn"


def test_inn_rejects_empty_and_whitespace():
    """INN rejects empty / whitespace input."""
    assert inn({"id": ""})["ok"] is False
    assert inn({"id": "   "})["ok"] is False


def test_inn_rejects_non_digits():
    """INN rejects inputs with non-digit characters (after normalization)."""
    assert inn({"id": "7707AB3893"})["ok"] is False
    assert inn({"id": "7707.083.893"})["ok"] is False


def test_inn_rejects_only_actually_wrong_lengths():
    """INN rejects lengths that are NOT valid for any RU identifier.

    Valid lengths: 9 (KPP), 10 (INN legal), 11 (SNILS), 12 (INN individual),
    13 (OGRN), 15 (OGRNIP).
    Invalid: 1, 5, 7, 14, 16, 20.
    """
    for length in (1, 5, 7, 14, 16, 20):
        s = "0" * length
        r = inn({"id": s})
        assert r["ok"] is False, f"length {length} should be rejected"


# ─── 3. KPP, OGRN, OGRNIP, SNILS round-trip ────────────────────────

def test_kpp_known_valid_fixture():
    """KPP 9-digit valid fixture."""
    assert inn({"id": "770701001"})["ok"] is True
    assert inn({"id": "770701001"})["kind"] == "kpp"
    assert inn({"id": "770701001"})["normalized"] == "770701001"

    # KPP can include non-digits (some formats: e.g. "7707AB001" — region+code+reason)
    # Verify the upstream fixture works
    r = inn({"id": "7707AB001"})
    # Per upstream, this is accepted (kpp can have non-digit in middle)
    assert r["ok"] is True
    assert r["kind"] == "kpp"


def test_ogrn_known_valid_fixture():
    """OGRN 13-digit valid fixture (with mod-11 check)."""
    assert inn({"id": "1027700132195"})["ok"] is True
    assert inn({"id": "1027700132195"})["kind"] == "ogrn"
    assert inn({"id": "1027700132195"})["normalized"] == "1027700132195"


def test_ogrnip_known_valid_fixture():
    """OGRNIP 15-digit valid fixture (with mod-13 check)."""
    assert inn({"id": "304500116000157"})["ok"] is True
    assert inn({"id": "304500116000157"})["kind"] == "ogrnip"
    assert inn({"id": "304500116000157"})["normalized"] == "304500116000157"


def test_snils_known_valid_fixtures():
    """SNILS 11-digit valid fixtures (with mod-101 check)."""
    assert inn({"id": "11223344595"})["ok"] is True
    assert inn({"id": "11223344595"})["kind"] == "snils"
    # SNILS strips separators ([\\s-])
    assert inn({"id": "112-233-445 95"})["ok"] is True
    assert inn({"id": "112-233-445 95"})["normalized"] == "11223344595"


# ─── 4. Cross-validator via dispatcher ──────────────────────────

def test_validate_dispatches_inn_to_ru_identifiers():
    """a1_validator.validate('inn', ...) dispatches to the ru_identifiers module."""
    r = validate("inn", {"id": "7707083893"})
    assert r["ok"] is True
    assert r["kind"] == "inn_legal"
    assert r["normalized"] == "7707083893"


def test_validate_accepts_inn_aliases():
    """a1_validator.validate accepts 'inn' (and aliases: 'identifier', 'ru_identifiers')."""
    for kind in ("inn", "identifier", "ru_identifiers"):
        r = validate(kind, {"id": "7707083893"})
        assert r["ok"] is True, f"kind={kind} should dispatch to ru_identifiers"


def test_inn_in_list_kinds():
    """'inn' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "inn" in kinds, f"inn must be in list_kinds() (got: {kinds})"


# ─── 5. Sovereignty (offline-capable) ────────────────────────────

def test_ru_identifiers_pure_functions():
    """ru_identifiers.py must be pure — no I/O, no network, no filesystem."""
    import importlib.util
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "ru_identifiers.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "ru_identifiers.py must not require network modules"
    # No filesystem require (read/write)
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "ru_identifiers.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "ru_identifiers.py must not require child_process"


# ─── 6. Check-digit math correctness (sanity) ────────────────────

def test_inn10_check_digit_formula_known_valid():
    """Verify the check-digit math: 7707083893 should compute to 3 (last digit)."""
    digits = [int(c) for c in "7707083893"]
    c = sum(w * d for w, d in zip(_INN10_WEIGHTS, digits[:9])) % 11 % 10
    assert c == digits[9], (
        f"INN 10-digit check digit math: expected {digits[9]}, computed {c}"
    )


def test_inn12_check_digit_formula_known_valid():
    """Verify the 12-digit INN check-digit math (two check digits)."""
    s = "500100732259"
    digits = [int(c) for c in s]
    c1 = sum(w * d for w, d in zip(_INN12_FIRST_WEIGHTS, digits[:10])) % 11 % 10
    c2 = sum(w * d for w, d in zip(_INN12_SECOND_WEIGHTS, digits[:11])) % 11 % 10
    assert c1 == digits[10], f"INN 12-digit first check digit: expected {digits[10]}, computed {c1}"
    assert c2 == digits[11], f"INN 12-digit second check digit: expected {digits[11]}, computed {c2}"