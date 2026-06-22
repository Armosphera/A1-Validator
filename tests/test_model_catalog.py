"""test_model_catalog.py — focused tests for the OpenRouter model catalog.

The vendored ``model_catalog`` module fetches the live OpenRouter /models
list and falls back to a static FALLBACK_MODELS tuple when egress is blocked.

Public API:
- ``FALLBACK_MODELS`` (tuple of 5 dicts) — static offline safety net
- ``_normalize_models(raw)`` — map OpenRouter payload → A1 shape
- ``ModelCatalog`` class:
  - ``__init__(safe_fetch, is_egress_allowed, openrouter)``
  - ``list_models(api_key, env) -> {online, source, reason, models}``
- ``create_model_catalog(safe_fetch, is_egress_allowed, openrouter)`` — factory
- ``validate(input)`` — uniform entry point (mirrors others)

Per the contract:
- ``FALLBACK_MODELS`` is the offline safety net (never remove)
- ``list_models`` returns ``{online: False, source: 'fallback', reason: ..., models: [...]}``
  when egress is blocked OR safeFetch fails OR the response is empty
- ``list_models`` returns ``{online: True, source: 'live', reason: None, models: [...]}``
  on success
- All HTTP goes through the injected ``safe_fetch`` (no raw `requests`/`httpx`)

Tests here complement test_validators.py::test_model_catalog (parametrized).
This file adds:
- 10 parametrized upstream eval_set verification (mirrors HHVH)
- 4 FALLBACK_MODELS tests (count, shapes, immutability)
- 6 _normalize_models tests (happy path, missing data, bad types, pricing)
- 5 ModelCatalog factory tests (valid, bad safe_fetch, bad is_egress, missing modelsUrl)
- 5 list_models tests (live, egress-blocked, http-502, network error, empty list)
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/model_catalog.py (the contract surface)
- tests/_eval_sets/model_catalog.json (canonical ground truth, 10 cases)
- autho://autoresearch-sboss/examples/model-catalog/workflow.py (MIT upstream)
- OpenRouter API spec (/models endpoint)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from a1_validator._vendored import model_catalog
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "model_catalog.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per OpenRouter /models) ────────────────

EXPECTED_FALLBACK_COUNT = 5     # Static offline safety net
EXPECTED_FALLBACK_HAS_CONTEXT = True  # Every model has context_length
EXPECTED_REQUIRED_FALLBACK_IDS = [
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5",
    "meta-llama/llama-3.1-70b-instruct",
]
EXPECTED_OPENROUTER_HOST = "openrouter.ai"  # (not in source but documented)


# ─── 2. Parametrized upstream eval set ───────────────────

def _dotted_get(d, dotted_key):
    """Get a nested value via dotted key. E.g. _dotted_get(d, 'a.b.c') → d['a']['b']['c']."""
    keys = dotted_key.split(".")
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_model_catalog_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result.

    Mirrors test_validators.py matching contract:
    - Subset equality (extra keys in actual are OK)
    - Dotted-path keys (e.g. 'lastRequest.method' → actual['lastRequest']['method'])
    """
    actual = model_catalog.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. FALLBACK_MODELS (the offline safety net) ─────────

def test_fallback_models_count():
    """FALLBACK_MODELS is a static tuple of exactly 5 models."""
    assert isinstance(model_catalog.FALLBACK_MODELS, tuple)
    assert len(model_catalog.FALLBACK_MODELS) == EXPECTED_FALLBACK_COUNT


def test_fallback_models_have_required_ids():
    """FALLBACK_MODELS includes the 5 expected model IDs."""
    actual_ids = {m["id"] for m in model_catalog.FALLBACK_MODELS}
    for required_id in EXPECTED_REQUIRED_FALLBACK_IDS:
        assert required_id in actual_ids, f"Missing fallback model: {required_id}"


def test_fallback_models_have_required_fields():
    """Each FALLBACK_MODELS entry has id, name, contextLength, pricing."""
    for m in model_catalog.FALLBACK_MODELS:
        assert "id" in m, f"FALLBACK model missing 'id': {m}"
        assert "name" in m, f"FALLBACK model missing 'name': {m}"
        assert "contextLength" in m, f"FALLBACK model missing 'contextLength': {m}"
        assert "pricing" in m, f"FALLBACK model missing 'pricing': {m}"
        # contextLength is an int > 0
        assert isinstance(m["contextLength"], (int, float)) and m["contextLength"] > 0, \
            f"FALLBACK model contextLength not positive: {m}"
        # pricing has prompt + completion (can be None for offline)
        assert "prompt" in m["pricing"]
        assert "completion" in m["pricing"]


def test_fallback_models_is_immutable():
    """FALLBACK_MODELS is a tuple (immutable)."""
    assert isinstance(model_catalog.FALLBACK_MODELS, tuple)
    # Tuples don't have .append / .pop
    with pytest.raises(AttributeError):
        model_catalog.FALLBACK_MODELS.append  # type: ignore[attr-defined]


# ─── 4. _normalize_models (OpenRouter → A1 shape) ──────

def test_normalize_models_happy_path():
    """_normalize_models maps OpenRouter /models payload to A1 shape."""
    raw = {
        "data": [
            {
                "id": "openai/gpt-4o",
                "name": "OpenAI: GPT-4o",
                "context_length": 128000,
                "pricing": {"prompt": "0.000005", "completion": "0.000015"},
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Anthropic: Claude 3.5 Sonnet",
                "context_length": 200000,
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
        ]
    }
    result = model_catalog._normalize_models(raw)
    assert len(result) == 2
    assert result[0]["id"] == "openai/gpt-4o"
    assert result[0]["name"] == "OpenAI: GPT-4o"
    assert result[0]["contextLength"] == 128000
    assert result[0]["pricing"] == {"prompt": "0.000005", "completion": "0.000015"}


def test_normalize_models_missing_data_returns_empty():
    """_normalize_models returns [] for missing 'data' key."""
    assert model_catalog._normalize_models({}) == []
    assert model_catalog._normalize_models({"data": []}) == []
    assert model_catalog._normalize_models(None) == []
    assert model_catalog._normalize_models("not a dict") == []


def test_normalize_models_skips_models_without_id():
    """_normalize_models skips entries without a string id."""
    raw = {
        "data": [
            {"id": "valid/model", "name": "Valid", "context_length": 1000, "pricing": {}},
            {"name": "No ID", "context_length": 1000, "pricing": {}},  # skipped
            {"id": "", "name": "Empty ID", "context_length": 1000, "pricing": {}},  # skipped
            {"id": 123, "name": "Numeric ID", "context_length": 1000, "pricing": {}},  # skipped
        ]
    }
    result = model_catalog._normalize_models(raw)
    assert len(result) == 1
    assert result[0]["id"] == "valid/model"


def test_normalize_models_uses_id_as_name_fallback():
    """_normalize_models uses id as name if name is missing/empty."""
    raw = {"data": [{"id": "test/model", "context_length": 1000, "pricing": {}}]}
    result = model_catalog._normalize_models(raw)
    assert result[0]["name"] == "test/model"


def test_normalize_models_handles_missing_context_length():
    """_normalize_models defaults contextLength to 0 if missing or invalid."""
    raw = {"data": [{"id": "test/model", "name": "Test", "pricing": {}}]}
    result = model_catalog._normalize_models(raw)
    assert result[0]["contextLength"] == 0


def test_normalize_models_handles_missing_pricing():
    """_normalize_models defaults pricing to {prompt: None, completion: None}."""
    raw = {"data": [{"id": "test/model", "name": "Test", "context_length": 1000}]}
    result = model_catalog._normalize_models(raw)
    assert result[0]["pricing"] == {"prompt": None, "completion": None}


# ─── 5. ModelCatalog factory (dependency injection) ────

def _make_mock_safe_fetch(response, status=200, ok=True, throw=False):
    """Build a mock safeFetch that records calls + returns canned response."""
    call_log = {"url": None, "options": None, "env": None}

    def safe_fetch(url, options, env):
        call_log["url"] = url
        call_log["options"] = options
        call_log["env"] = env
        if throw:
            err = RuntimeError("simulated network error")
            err.code = "ECONNREFUSED"
            raise err
        return {"ok": ok, "status": status, "json": lambda: response}

    return safe_fetch, call_log


def _make_catalog(openrouter=None, safe_fetch=None, is_egress_allowed=None):
    """Build a ModelCatalog with sensible defaults."""
    if openrouter is None:
        openrouter = {"modelsUrl": "https://openrouter.ai/api/v1/models", "referer": "x", "title": "y"}
    if safe_fetch is None:
        safe_fetch, _ = _make_mock_safe_fetch({"data": []})
    if is_egress_allowed is None:
        is_egress_allowed = lambda env: True
    return model_catalog.create_model_catalog(safe_fetch, is_egress_allowed, openrouter), safe_fetch


def test_create_model_catalog_with_valid_inputs():
    """create_model_catalog succeeds with valid safe_fetch + is_egress + openrouter."""
    catalog, _ = _make_catalog()
    assert catalog is not None


def test_create_model_catalog_rejects_non_callable_safe_fetch():
    """create_model_catalog raises TypeError if safe_fetch is not callable."""
    with pytest.raises(TypeError) as exc_info:
        model_catalog.create_model_catalog(
            "not a function", lambda env: True, {"modelsUrl": "x"},
        )
    assert "safe_fetch" in str(exc_info.value).lower()


def test_create_model_catalog_rejects_non_callable_is_egress():
    """create_model_catalog raises TypeError if is_egress_allowed is not callable."""
    with pytest.raises(TypeError) as exc_info:
        model_catalog.create_model_catalog(
            _make_mock_safe_fetch({"data": []})[0],
            "not a function",
            {"modelsUrl": "x"},
        )
    assert "egress" in str(exc_info.value).lower() or "is_egress" in str(exc_info.value).lower()


def test_create_model_catalog_rejects_missing_modelsUrl():
    """create_model_catalog raises TypeError if openrouter.modelsUrl is missing."""
    with pytest.raises(TypeError) as exc_info:
        model_catalog.create_model_catalog(
            _make_mock_safe_fetch({"data": []})[0],
            lambda env: True,
            {"referer": "x", "title": "y"},  # no modelsUrl
        )
    assert "modelsurl" in str(exc_info.value).lower()


def test_create_model_catalog_rejects_empty_openrouter():
    """create_model_catalog raises TypeError if openrouter is None/empty."""
    with pytest.raises(TypeError):
        model_catalog.create_model_catalog(
            _make_mock_safe_fetch({"data": []})[0],
            lambda env: True,
            None,
        )


# ─── 6. list_models (the 4 source paths) ─────────────────

def test_list_models_live_source_on_success():
    """list_models returns {online: True, source: 'live'} on successful fetch."""
    safe_fetch, call_log = _make_mock_safe_fetch({
        "data": [
            {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000, "pricing": {}},
        ],
    })
    catalog, _ = _make_catalog(safe_fetch=safe_fetch)
    result = catalog.list_models(api_key="sk-test", env={})
    assert result["online"] is True
    assert result["source"] == "live"
    assert result["reason"] is None
    assert len(result["models"]) == 1
    assert result["models"][0]["id"] == "openai/gpt-4o"
    # The safe_fetch was called with the right URL
    assert call_log["url"] == "https://openrouter.ai/api/v1/models"
    assert call_log["options"]["method"] == "GET"
    assert call_log["options"]["headers"]["Authorization"] == "Bearer sk-test"


def test_list_models_fallback_when_egress_blocked():
    """list_models returns FALLBACK when is_egress_allowed returns False."""
    safe_fetch, call_log = _make_mock_safe_fetch({"data": []})
    catalog, _ = _make_catalog(
        safe_fetch=safe_fetch,
        is_egress_allowed=lambda env: False,  # egress blocked
    )
    result = catalog.list_models(api_key="sk-test", env={})
    assert result["online"] is False
    assert result["source"] == "fallback"
    assert result["reason"] == "egress-blocked"
    assert len(result["models"]) == 5  # FALLBACK_MODELS
    # safe_fetch was NEVER called (egress blocked before fetch)
    assert call_log["url"] is None


def test_list_models_fallback_on_http_error():
    """list_models returns FALLBACK with http-XXX reason on HTTP error."""
    safe_fetch, _ = _make_mock_safe_fetch({}, status=502, ok=False)
    catalog, _ = _make_catalog(safe_fetch=safe_fetch)
    result = catalog.list_models(api_key="sk-test", env={})
    assert result["online"] is False
    assert result["source"] == "fallback"
    assert result["reason"] == "http-502"
    assert len(result["models"]) == 5


def test_list_models_fallback_on_network_error():
    """list_models returns FALLBACK on network exception."""
    safe_fetch, _ = _make_mock_safe_fetch({}, throw=True)
    catalog, _ = _make_catalog(safe_fetch=safe_fetch)
    result = catalog.list_models(api_key="sk-test", env={})
    assert result["online"] is False
    assert result["source"] == "fallback"
    assert result["reason"] == "ECONNREFUSED"
    assert len(result["models"]) == 5


def test_list_models_fallback_on_empty_response():
    """list_models returns FALLBACK with 'empty-list' reason when response is empty."""
    safe_fetch, _ = _make_mock_safe_fetch({"data": []})
    catalog, _ = _make_catalog(safe_fetch=safe_fetch)
    result = catalog.list_models(api_key="sk-test", env={})
    assert result["online"] is False
    assert result["source"] == "fallback"
    assert result["reason"] == "empty-list"
    assert len(result["models"]) == 5


def test_list_models_omits_auth_header_when_no_api_key():
    """list_models doesn't send Authorization header if api_key is empty."""
    safe_fetch, call_log = _make_mock_safe_fetch({"data": []})
    catalog, _ = _make_catalog(safe_fetch=safe_fetch)
    catalog.list_models(api_key="", env={})
    assert "Authorization" not in call_log["options"]["headers"]


# ─── 7. Cross-validator via dispatcher ─────────────────

def test_validate_dispatches_model_catalog():
    """a1_validator.validate('model_catalog', ...) dispatches correctly."""
    r = validate("model_catalog", {
        "egressAllowed": True,
        "safeFetchResponse": {
            "data": [
                {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000, "pricing": {}},
            ],
        },
        "safeFetchStatus": 200,
        "safeFetchOk": True,
        "openrouter": {"modelsUrl": "https://openrouter.ai/api/v1/models"},
    })
    assert r["online"] is True
    assert r["source"] == "live"
    assert r["modelsCount"] == 1


def test_model_catalog_in_list_kinds():
    """'model_catalog' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "model_catalog" in kinds, f"model_catalog must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (offline-capable) ────────────────

def test_model_catalog_pure_functions():
    """model_catalog.py must be pure — no raw HTTP, no I/O."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "model_catalog.py"
    src = src_path.read_text()

    # No raw HTTP module require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net)', src), \
        "model_catalog.py must not require http/https/net modules"
    # No raw HTTP library
    assert not re.search(r'\b(httpx|aiohttp|requests|urllib3)\b', src), \
        "model_catalog.py must not use any HTTP library directly"
    # The only fetch must be the injected safe_fetch (check for `self._safe_fetch`)
    assert "self._safe_fetch" in src, \
        "model_catalog.py must use self._safe_fetch (injected) for all HTTP calls"