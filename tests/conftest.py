"""Pytest fixtures and helpers for a1_validator tests.

Vendored eval sets live under `tests/_eval_sets/<name>.json` — one file per
upstream autoresearch-sboss example. Each file is a JSON array of
``{input, expected}`` cases, copied verbatim from the upstream
``examples/<name>/eval_set.json`` so the Python port is contract-locked to
the same baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# `tests/_eval_sets/` sits next to this conftest.py.
TESTS_DIR = Path(__file__).resolve().parent
EVAL_SETS_DIR = TESTS_DIR / "_eval_sets"


def vendored_eval_set(name: str) -> list[dict[str, Any]]:
    """Load ``tests/_eval_sets/<name>.json`` and return its case list.

    Each case is ``{"input": <dict>, "expected": <dict>}``. The shape mirrors
    the upstream autoresearch-sboss eval harness (which feeds a JSON object
    as the validator input and asserts deep equality on the output dict).
    """
    path = EVAL_SETS_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def eval_set():
    """Per-test factory: ``eval_set("hhvh")`` → case list."""
    return vendored_eval_set


def _id_for(case_index: int, case: dict[str, Any]) -> str:
    """Build a short, stable pytest id from the input payload."""
    inp = case.get("input", {})
    if isinstance(inp, dict):
        # Use the first scalar-ish value as a human hint, fall back to case#
        for v in inp.values():
            if isinstance(v, (str, int, float, bool)):
                return f"case{case_index}-{v!s}"[:40]
    return f"case{case_index}"


@pytest.fixture
def cases_for():
    """Per-test factory: ``cases_for("hhvh")`` → list of pytest.param items.

    Each item carries ``id=_id_for(...)`` so the pytest output traces back to
    the offending input instead of just ``case0``/``case1``.
    """
    def _build(name: str) -> list[pytest.param]:
        return [
            pytest.param(case["input"], case["expected"], id=_id_for(i, case))
            for i, case in enumerate(vendored_eval_set(name))
        ]
    return _build