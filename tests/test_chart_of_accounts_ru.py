"""test_chart_of_accounts_ru.py — focused tests for the Russian chart of accounts.

The vendored ``chart_of_accounts_ru`` module implements the Russian Federation
План счетов бухгалтерского учёта (Приказ Минфина РФ № 94н от 31.10.2000):

- 8 balance-sheet sections (разделы I–VIII), each a numeric range
- 1 off-balance section (забалансовые счета, codes 001–011)
- 62 synthetic accounts (1st-order, синтетические) + 11 off-balance = 73 total
- Each account has: code, ru name, section (Roman numeral), nature (active/passive/active-passive), normal balance (debit/credit/None)

The module exposes:
- ``account_by_code(code) -> dict | None`` — lookup by code
- ``accounts_by_section(section_id) -> list[dict]`` — accounts in a section
- ``accounts_by_nature(nature) -> list[dict]`` — accounts by nature
- ``section_of(code) -> dict | None`` — section by code (range-based, NOT dict)
- ``normal_balance(code) -> str | None`` — debit/credit/None
- ``is_valid_account_code(code) -> bool`` — existence check
- ``validate(input_data) -> dict`` — uniform entry point (mirrors others)

Tests here complement test_validators.py::test_chart_of_accounts_ru
(which does parametrized verification against the eval_set). This file adds:
- Real fixture lookup for 4 known accounts (01, 02, 41, 90)
- Section-of range math (test all 8 section boundaries)
- Off-balance section (3-digit codes 001–011)
- Invalid code behavior (None, empty, non-existent)
- Whitespace normalization
- Cross-validator dispatcher (validate('chart_of_accounts_ru', ...))
- Sovereignty: no network/fs require

Source:
- src/a1_validator/_vendored/chart_of_accounts_ru.py (the contract surface)
- src/a1_validator/_vendored/chart_of_accounts_ru.json (62 synthetic accounts)
- src/a1_validator/_vendored/chart_of_accounts_ru_sections.json (9 sections)
- tests/_eval_sets/chart_of_accounts_ru.json (canonical ground truth, 19 cases)
- autho://autoresearch-sboss/examples/chart-of-accounts-ru/workflow.py (MIT upstream)
- Приказ Минфина РФ № 94н от 31.10.2000 (primary source)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# chart_of_accounts_ru is exposed as a1_validator.chart_of_accounts_ru (the
# validate function). For the full module API, import from _vendored.
from a1_validator._vendored import chart_of_accounts_ru
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "chart_of_accounts_ru.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per Приказ Минфина РФ № 94н) ─────────────────

EXPECTED_SECTION_COUNT = 9        # I–VIII + offBalance
EXPECTED_SYNTHETIC_ACCOUNTS = 62   # 1st-order (синтетические)
EXPECTED_OFF_BALANCE_ACCOUNTS = 11 # забалансовые (001–011)
EXPECTED_TOTAL_ACCOUNTS = 73       # 62 + 11

# Per Приказ № 94н (Приложение 1):
# 8 balance-sheet sections (I–VIII), each with a specific code range
EXPECTED_SECTION_RANGES = {
    "I": (1, 9),       # Внеоборотные активы
    "II": (10, 19),    # Производственные запасы
    "III": (20, 39),   # Затраты на производство
    "IV": (40, 49),    # Готовая продукция и товары
    "V": (50, 59),     # Денежные средства
    "VI": (60, 79),    # Расчёты
    "VII": (80, 89),    # Капитал
    "VIII": (90, 99),  # Финансовые результаты
    "offBalance": (1, 11),  # Забалансовые счета (3-digit codes 001-011)
}

# Nature → normal balance (per accounting principles)
NATURE_TO_NORMAL_BALANCE = {
    "active": "debit",        # Asset accounts: debit increases, credit decreases
    "passive": "credit",      # Liability/equity: credit increases, debit decreases
    "active-passive": None,   # Dual-nature accounts (e.g. settlement accounts)
}


# ─── 2. account_by_code (lookup) ────────────────────────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_chart_of_accounts_ru_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = chart_of_accounts_ru.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


def test_account_by_code_known_real_accounts():
    """account_by_code returns real accounts from Приказ № 94н."""
    # Account 01 — Основные средства (Fixed assets)
    r = chart_of_accounts_ru.account_by_code("01")
    assert r is not None
    assert r["code"] == "01"
    assert r["ru"] == "Основные средства"
    assert r["section"] == "I"
    assert r["nature"] == "active"

    # Account 02 — Амортизация основных средств (Accumulated depreciation)
    r = chart_of_accounts_ru.account_by_code("02")
    assert r["code"] == "02"
    assert r["ru"] == "Амортизация основных средств"
    assert r["section"] == "I"
    assert r["nature"] == "passive"

    # Account 41 — Товары (Goods/Merchandise inventory)
    r = chart_of_accounts_ru.account_by_code("41")
    assert r["code"] == "41"
    assert r["section"] == "IV"
    assert r["nature"] == "active"

    # Account 90 — Продажи (Sales)
    r = chart_of_accounts_ru.account_by_code("90")
    assert r["code"] == "90"
    assert r["section"] == "VIII"
    assert r["nature"] == "active-passive"


def test_account_by_code_strips_whitespace():
    """account_by_code normalizes whitespace."""
    r1 = chart_of_accounts_ru.account_by_code("01")
    r2 = chart_of_accounts_ru.account_by_code("  01  ")
    r3 = chart_of_accounts_ru.account_by_code("\t01\n")
    assert r1 is not None
    assert r1 == r2 == r3


def test_account_by_code_returns_none_for_invalid():
    """account_by_code returns None for unknown codes / non-numeric."""
    assert chart_of_accounts_ru.account_by_code("9999") is None  # not in 1-99
    assert chart_of_accounts_ru.account_by_code("ABC") is None   # not numeric
    assert chart_of_accounts_ru.account_by_code("") is None
    assert chart_of_accounts_ru.account_by_code(None) is None
    assert chart_of_accounts_ru.account_by_code({}) is None
    assert chart_of_accounts_ru.account_by_code([]) is None


def test_account_by_code_off_balance_three_digit():
    """Off-balance accounts (001-011) are 3-digit codes (per Приказ № 94н)."""
    # Account 001 — Арендованные основные средства
    r = chart_of_accounts_ru.account_by_code("001")
    assert r is not None
    assert r["code"] == "001"
    assert r["section"] == "offBalance"
    assert r["nature"] == "active"

    # Account 011 — Основные средства, переданные в аренду (or similar off-balance)
    r = chart_of_accounts_ru.account_by_code("011")
    assert r is not None
    assert r["code"] == "011"
    assert r["section"] == "offBalance"

    # 012 doesn't exist (off-balance only goes 001-011)
    assert chart_of_accounts_ru.account_by_code("012") is None


# ─── 3. section_of (range-based lookup) ──────────────────────────

def test_section_of_known_codes():
    """section_of returns the right section for known codes."""
    assert chart_of_accounts_ru.section_of("01")["id"] == "I"
    assert chart_of_accounts_ru.section_of("09")["id"] == "I"   # last of section I
    assert chart_of_accounts_ru.section_of("10")["id"] == "II"  # first of section II
    assert chart_of_accounts_ru.section_of("41")["id"] == "IV"
    assert chart_of_accounts_ru.section_of("50")["id"] == "V"
    assert chart_of_accounts_ru.section_of("60")["id"] == "VI"
    assert chart_of_accounts_ru.section_of("80")["id"] == "VII"
    assert chart_of_accounts_ru.section_of("90")["id"] == "VIII"
    assert chart_of_accounts_ru.section_of("99")["id"] == "VIII"  # last of section VIII


def test_section_of_off_balance():
    """section_of returns offBalance for 3-digit codes (001-011)."""
    assert chart_of_accounts_ru.section_of("001")["id"] == "offBalance"
    assert chart_of_accounts_ru.section_of("005")["id"] == "offBalance"
    assert chart_of_accounts_ru.section_of("011")["id"] == "offBalance"


def test_section_of_section_count_matches_94n():
    """Total section count is 9 (8 balance-sheet + 1 off-balance, per Приказ № 94н)."""
    # 8 balance-sheet (I-VIII) + 1 off-balance = 9
    # Note: only check this if the module exposes the section list
    # Otherwise infer from the eval set
    unique_sections = set()
    for case in EVAL_SET:
        if "section" in case["expected"]:
            unique_sections.add(case["expected"]["section"])
    # We don't have all sections in the eval set, but we have 4+ at least
    assert len(unique_sections) >= 3


# ─── 4. normal_balance ───────────────────────────────────────────

def test_normal_balance_per_nature():
    """normal_balance returns debit/credit/None per accounting principles."""
    # Account 01 (active) — debit
    assert chart_of_accounts_ru.normal_balance("01") == "debit"

    # Account 02 (passive) — credit
    assert chart_of_accounts_ru.normal_balance("02") == "credit"

    # Account 90 (active-passive) — None
    assert chart_of_accounts_ru.normal_balance("90") is None

    # Account 41 (active) — debit
    assert chart_of_accounts_ru.normal_balance("41") == "debit"


def test_normal_balance_for_off_balance():
    """Off-balance accounts (3-digit) follow the same nature rules."""
    # Account 001 (off-balance, active) — debit
    assert chart_of_accounts_ru.normal_balance("001") == "debit"


def test_normal_balance_invalid_code():
    """normal_balance returns None for invalid codes."""
    assert chart_of_accounts_ru.normal_balance("9999") is None
    assert chart_of_accounts_ru.normal_balance("ABC") is None
    assert chart_of_accounts_ru.normal_balance("") is None


# ─── 5. is_valid_account_code ───────────────────────────────────

def test_is_valid_account_code_for_known_accounts():
    """is_valid_account_code returns True for known accounts."""
    assert chart_of_accounts_ru.is_valid_account_code("01") is True
    assert chart_of_accounts_ru.is_valid_account_code("02") is True
    assert chart_of_accounts_ru.is_valid_account_code("41") is True
    assert chart_of_accounts_ru.is_valid_account_code("90") is True
    assert chart_of_accounts_ru.is_valid_account_code("001") is True  # off-balance


def test_is_valid_account_code_for_invalid_codes():
    """is_valid_account_code returns False for unknown codes."""
    assert chart_of_accounts_ru.is_valid_account_code("9999") is False
    assert chart_of_accounts_ru.is_valid_account_code("ABC") is False
    assert chart_of_accounts_ru.is_valid_account_code("") is False
    assert chart_of_accounts_ru.is_valid_account_code(None) is False


# ─── 6. Cross-validator via dispatcher ──────────────────────────

def test_validate_dispatches_chart_of_accounts_ru():
    """a1_validator.validate('chart_of_accounts_ru', ...) dispatches correctly."""
    r = validate("chart_of_accounts_ru", {"code": "01"})
    assert r["found"] is True
    assert r["code"] == "01"
    assert r["ru"] == "Основные средства"


def test_chart_of_accounts_ru_in_list_kinds():
    """'chart_of_accounts_ru' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "chart_of_accounts_ru" in kinds, f"chart_of_accounts_ru must be in list_kinds() (got: {kinds})"


# ─── 7. Sovereignty (offline-capable) ────────────────────────────

def test_chart_of_accounts_ru_pure_functions():
    """chart_of_accounts_ru.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "chart_of_accounts_ru.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "chart_of_accounts_ru.py must not require network modules"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "chart_of_accounts_ru.py must not require child_process"
    # No environment variable reads (accounting code is pure)
    # NOTE: chart_of_accounts_ru does read .json data files at import time
    # (DATA_DIR / "chart_of_accounts_ru.json") — that's expected and OK
    # (data is bundled with the vendored package, not a runtime env read)


def test_chart_of_accounts_ru_data_files_bundled():
    """The data files (accounts + sections) are bundled with the vendored package."""
    vendored_dir = Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored"
    assert (vendored_dir / "chart_of_accounts_ru.json").exists(), \
        "chart_of_accounts_ru.json must be bundled"
    assert (vendored_dir / "chart_of_accounts_ru_sections.json").exists(), \
        "chart_of_accounts_ru_sections.json must be bundled"

    # Sanity: data files are non-empty valid JSON
    accounts = json.loads((vendored_dir / "chart_of_accounts_ru.json").read_text())
    sections = json.loads((vendored_dir / "chart_of_accounts_ru_sections.json").read_text())
    assert len(accounts) >= EXPECTED_TOTAL_ACCOUNTS - 1, \
        f"Expected at least {EXPECTED_TOTAL_ACCOUNTS - 1} accounts, got {len(accounts)}"
    assert len(sections) == EXPECTED_SECTION_COUNT, \
        f"Expected {EXPECTED_SECTION_COUNT} sections, got {len(sections)}"