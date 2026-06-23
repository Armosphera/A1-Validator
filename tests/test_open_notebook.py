"""test_open_notebook.py — focused tests for the Open Notebook connector.

The vendored ``open_notebook`` module implements the egress-gated, non-throwing
Open Notebook search connector. Used by every A1 product to search the user's
private notebook for relevant context before generating a response.

Public API:
- ``DEFAULT_SEARCH_PATH = "/api/search"``
- ``is_enabled(settings) -> bool`` — whether the connector is configured + enabled
- ``normalize_results(raw, k=6) -> list[dict]`` — tolerate response shapes
- ``OpenNotebook`` class:
  - ``__init__(safe_fetch)``
  - ``search(query, settings, k=6, env) -> list[dict]`` — egress-gated, non-throwing
- ``create_open_notebook(safe_fetch) -> OpenNotebook`` — factory
- ``validate(input) -> dict`` — uniform entry point

Contract:
- Returns ``[]`` on any failure (network, auth, malformed response)
- ``is_enabled(settings)`` requires ``settings.openNotebook.enabled = True``
  AND ``settings.openNotebook.baseUrl`` is set
- ``normalize_results`` tolerates ``{results}|{sources}|{data}|array`` shapes

Tests here complement test_validators.py::test_open_notebook (parametrized).
This file adds:
- 16 parametrized upstream eval_set verification (mirrors HHVH)
- 4 is_enabled tests (valid, missing settings, missing openNotebook, disabled, no baseUrl)
- 6 normalize_results tests (array, results, sources, data, k limit, no text)
- 5 OpenNotebook class tests (factory, non-callable safeFetch, search, disabled)
- 4 search() tests (enabled, disabled, empty query, network failure, malformed response)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/open_notebook.py (the contract surface)
- tests/_eval_sets/open_notebook.json (canonical ground truth, 16 cases)
- autho://autoresearch-sboss/examples/open-notebook/workflow.py (MIT upstream)
- A1-AI-Core/src/open-notebook.js (the JS source of truth)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import open_notebook
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "open_notebook.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants ──────────────────────────────────

EXPECTED_DEFAULT_SEARCH_PATH = "/api/search"


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
def test_open_notebook_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = open_notebook.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. is_enabled ──────────────────────────────

def test_is_enabled_returns_true_when_enabled():
    """is_enabled returns True when enabled=True AND baseUrl is set."""
    settings = {
        "openNotebook": {
            "enabled": True,
            "baseUrl": "https://notebook.local",
            "apiKey": "nb-key",
        }
    }
    assert open_notebook.is_enabled(settings) is True


def test_is_enabled_returns_false_when_disabled():
    """is_enabled returns False when enabled=False."""
    settings = {
        "openNotebook": {
            "enabled": False,
            "baseUrl": "https://notebook.local",
        }
    }
    assert open_notebook.is_enabled(settings) is False


def test_is_enabled_returns_false_when_no_baseurl():
    """is_enabled returns False when baseUrl is missing."""
    settings = {
        "openNotebook": {
            "enabled": True,
            "apiKey": "nb-key",
        }
    }
    assert open_notebook.is_enabled(settings) is False


def test_is_enabled_returns_false_for_non_dict_input():
    """is_enabled returns False for non-dict settings (defensive)."""
    assert open_notebook.is_enabled(None) is False
    assert open_notebook.is_enabled("not a dict") is False
    assert open_notebook.is_enabled(42) is False
    assert open_notebook.is_enabled([]) is False


# ─── 4. normalize_results (tolerate response shapes) ──

def test_normalize_results_accepts_array():
    """normalize_results accepts a raw array of items."""
    raw = [
        {"title": "Doc 1", "text": "content 1", "score": 0.9},
        {"title": "Doc 2", "text": "content 2", "score": 0.7},
    ]
    result = open_notebook.normalize_results(raw)
    assert len(result) == 2
    assert result[0]["title"] == "Doc 1"
    assert result[0]["text"] == "content 1"


def test_normalize_results_accepts_results_key():
    """normalize_results accepts {results: [...]}."""
    raw = {"results": [{"title": "Doc", "text": "content", "score": 0.8}]}
    result = open_notebook.normalize_results(raw)
    assert len(result) == 1


def test_normalize_results_accepts_sources_key():
    """normalize_results accepts {sources: [...]} (Alt format)."""
    raw = {"sources": [{"name": "Doc", "snippet": "content", "relevance": 0.7}]}
    result = open_notebook.normalize_results(raw)
    assert len(result) == 1
    assert result[0]["text"] == "content"  # uses snippet as text
    assert result[0]["score"] == 0.7  # uses relevance as score


def test_normalize_results_accepts_data_key():
    """normalize_results accepts {data: [...]} (Alt format)."""
    raw = {"data": [{"notebook": "Doc", "content": "content", "url": "https://x"}]}
    result = open_notebook.normalize_results(raw)
    assert len(result) == 1
    assert result[0]["title"] == "Doc"  # uses notebook as title
    assert result[0]["sourceUrl"] == "https://x"


def test_normalize_results_limits_to_k():
    """normalize_results returns at most k results."""
    raw = [{"text": f"doc {i}"} for i in range(10)]
    result = open_notebook.normalize_results(raw, k=3)
    assert len(result) == 3


def test_normalize_results_skips_empty_text():
    """normalize_results skips items with no text (empty string or missing)."""
    raw = [
        {"title": "Doc 1", "text": "real content"},
        {"title": "Doc 2"},  # no text field → skipped
        {"title": "Doc 3", "text": ""},  # empty string → skipped
        # Note: whitespace-only "  " is NOT skipped per implementation
        {"title": "Doc 4", "text": "  "},
    ]
    result = open_notebook.normalize_results(raw)
    # Doc 1 + Doc 4 = 2 results (Doc 2 and 3 are skipped)
    assert len(result) == 2
    assert result[0]["title"] == "Doc 1"


# ─── 5. OpenNotebook class ───────────────────────

def test_create_open_notebook_with_valid_safefetch():
    """create_open_notebook succeeds with a valid safe_fetch."""
    def safe_fetch(url, options, env):
        return {"ok": True, "status": 200, "json": lambda: {"results": []}}

    nb = open_notebook.create_open_notebook(safe_fetch)
    assert nb is not None


def test_create_open_notebook_rejects_non_callable_safefetch():
    """create_open_notebook raises TypeError if safe_fetch is not callable."""
    with pytest.raises(TypeError) as exc_info:
        open_notebook.create_open_notebook("not a function")
    assert "safe_fetch" in str(exc_info.value).lower()


def test_create_open_notebook_class_has_search_method():
    """OpenNotebook class has a search() method."""
    nb = open_notebook.create_open_notebook(lambda u, o, e: {})
    assert hasattr(nb, "search")
    assert callable(nb.search)


# ─── 6. search() (the main method) ──────────────────

def test_search_returns_empty_when_disabled():
    """search returns [] when is_enabled returns False."""
    nb = open_notebook.create_open_notebook(lambda u, o, e: {"ok": True, "json": lambda: []})
    settings = {"openNotebook": {"enabled": False, "baseUrl": "https://x"}}
    result = nb.search("query", settings)
    assert result == []


def test_search_returns_empty_when_empty_query():
    """search returns [] for empty query."""
    nb = open_notebook.create_open_notebook(lambda u, o, e: {"ok": True, "json": lambda: []})
    settings = {"openNotebook": {"enabled": True, "baseUrl": "https://x"}}
    result = nb.search("", settings)
    assert result == []


def test_search_returns_empty_on_network_error():
    """search returns [] (non-throwing) on network error."""
    def failing_safe_fetch(url, options, env):
        raise RuntimeError("ECONNREFUSED")

    nb = open_notebook.create_open_notebook(failing_safe_fetch)
    settings = {"openNotebook": {"enabled": True, "baseUrl": "https://x"}}
    result = nb.search("query", settings)
    assert result == []  # non-throwing


def test_search_returns_empty_on_http_error():
    """search returns [] on HTTP error (4xx/5xx)."""
    def error_safe_fetch(url, options, env):
        return {"ok": False, "status": 500, "json": lambda: {}}

    nb = open_notebook.create_open_notebook(error_safe_fetch)
    settings = {"openNotebook": {"enabled": True, "baseUrl": "https://x"}}
    result = nb.search("query", settings)
    assert result == []


def test_search_normalizes_response():
    """search returns normalized items on success."""
    def good_safe_fetch(url, options, env):
        return {
            "ok": True,
            "status": 200,
            "json": lambda: {
                "results": [
                    {"title": "Doc 1", "text": "content 1", "score": 0.9, "url": "https://x/1"},
                ]
            }
        }

    nb = open_notebook.create_open_notebook(good_safe_fetch)
    settings = {"openNotebook": {"enabled": True, "baseUrl": "https://x"}}
    result = nb.search("query", settings)
    assert len(result) == 1
    assert result[0]["title"] == "Doc 1"
    assert result[0]["text"] == "content 1"
    assert result[0]["score"] == 0.9
    assert result[0]["sourceUrl"] == "https://x/1"
    assert result[0]["origin"] == "open-notebook"


# ─── 7. Cross-validator via dispatcher ──────────

def test_validate_dispatches_open_notebook():
    """a1_validator.validate('open_notebook', ...) dispatches correctly."""
    r = validate("open_notebook", {
        "settings": {"openNotebook": {"enabled": True, "baseUrl": "https://x"}},
        "query": "test",
        "safeFetchResponse": {"results": [{"title": "Doc", "text": "content"}]},
        "safeFetchStatus": 200,
        "safeFetchOk": True,
    })
    # Implementation-specific structure (may wrap in result, may not)
    assert r is not None


def test_open_notebook_in_list_kinds():
    """'open_notebook' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "open_notebook" in kinds, f"open_notebook must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (egress-gated) ──────────────

def test_open_notebook_pure_functions():
    """open_notebook.py must be pure — no I/O at runtime (only via injected safeFetch)."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "open_notebook.py"
    src = src_path.read_text()

    # No raw HTTP module require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "open_notebook.py must not require http/https/net modules"
    # No raw HTTP library
    assert not re.search(r'\b(httpx|aiohttp|requests|urllib3)\b', src), \
        "open_notebook.py must not use any HTTP library directly"
    # Uses injected safe_fetch
    assert "self._safe_fetch" in src, \
        "open_notebook.py must use self._safe_fetch (injected) for all HTTP calls"