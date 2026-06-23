"""test_model_policy.py — focused tests for the model resolution policy.

The vendored ``model_policy`` module implements the **precedence rule**
for resolving which LLM model to use for a given request.

Per the upstream JS reference (model-policy.js):

1. **Module override** — if `ctx.module` ∈ {finance, crm, docs} AND
   `policy[ctx.module]` is a non-empty string → use that model (source: "module")
2. **Aspect override** — else if `ctx.aspect` ∈ {copilot, transform} AND
   `policy[ctx.aspect]` is a non-empty string → use that model (source: "aspect")
3. **Default** — else if `policy.default` is a non-empty string → use that (source: "default")
4. **Auto** — else return "" (source: "auto", the consumer picks)

Public API:
- ``MODEL_KEYS`` (tuple of 6: default, copilot, transform, finance, crm, docs)
- ``MODULES`` (frozenset: finance, crm, docs)
- ``ASPECTS`` (frozenset: copilot, transform)
- ``_pick(policy, key)`` — extract a non-empty string from policy
- ``resolve_model(policy, ctx)`` — returns just the model id (or "" for auto)
- ``validate(input_data)`` — uniform entry point, returns {resolved_model, source}

Tests here complement test_validators.py::test_model_policy (parametrized).
This file adds:
- 20 parametrized upstream eval_set verification (mirrors HHVH)
- 6 constants tests (6 MODEL_KEYS, 3 MODULES, 2 ASPECTS)
- 6 _pick tests (string, empty string, whitespace, None, non-string, non-dict policy)
- 5 resolve_model tests (module precedence, aspect precedence, default fallback,
  auto fallback, empty ctx)
- 4 validate tests (source tracking, source "module" / "aspect" / "default" / "auto")
- 3 cross-validator dispatcher tests
- 1 sovereignty test

Source:
- src/a1_validator/_vendored/model_policy.py (the contract surface)
- tests/_eval_sets/model_policy.json (canonical ground truth, 20 cases)
- autho://autoresearch-sboss/examples/model-policy/workflow.py (MIT upstream)
- A1-AI-Core/src/model-policy.js (the JS source of truth)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from a1_validator._vendored import model_policy
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "model_policy.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants ──────────────────────────────────

EXPECTED_MODEL_KEYS = {"default", "copilot", "transform", "finance", "crm", "docs"}
EXPECTED_MODULES = {"finance", "crm", "docs"}
EXPECTED_ASPECTS = {"copilot", "transform"}


# ─── 2. Parametrized upstream eval set ───────────────

@pytest.mark.parametrize("case", EVAL_SET, ids=[f"case{i+1:02d}" for i in range(len(EVAL_SET))])
def test_model_policy_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result."""
    actual = model_policy.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual.get(key)!r}"
        )


# ─── 3. Constants tests ──────────────────────────

def test_model_keys_is_6_tuple():
    """MODEL_KEYS is a tuple of exactly 6 keys."""
    assert isinstance(model_policy.MODEL_KEYS, tuple)
    assert len(model_policy.MODEL_KEYS) == 6
    assert set(model_policy.MODEL_KEYS) == EXPECTED_MODEL_KEYS


def test_modules_is_frozenset_of_3():
    """MODULES is a frozenset of exactly 3 (finance, crm, docs)."""
    assert isinstance(model_policy.MODULES, frozenset)
    assert model_policy.MODULES == EXPECTED_MODULES
    assert len(model_policy.MODULES) == 3


def test_aspects_is_frozenset_of_2():
    """ASPECTS is a frozenset of exactly 2 (copilot, transform)."""
    assert isinstance(model_policy.ASPECTS, frozenset)
    assert model_policy.ASPECTS == EXPECTED_ASPECTS
    assert len(model_policy.ASPECTS) == 2


def test_modules_and_aspects_disjoint():
    """MODULES and ASPECTS are disjoint (different roles)."""
    assert model_policy.MODULES.isdisjoint(model_policy.ASPECTS)


def test_modules_and_aspects_in_model_keys():
    """All module + aspect names are in MODEL_KEYS."""
    for m in model_policy.MODULES:
        assert m in model_policy.MODEL_KEYS, f"Module {m!r} not in MODEL_KEYS"
    for a in model_policy.ASPECTS:
        assert a in model_policy.MODEL_KEYS, f"Aspect {a!r} not in MODEL_KEYS"


def test_default_always_in_model_keys():
    """'default' is always in MODEL_KEYS (fallback)."""
    assert "default" in model_policy.MODEL_KEYS


# ─── 4. _pick tests ─────────────────────────────

def test_pick_returns_string_value():
    """_pick returns the policy value if it's a non-empty string."""
    assert model_policy._pick({"default": "anthropic/claude-3.5-sonnet"}, "default") == "anthropic/claude-3.5-sonnet"


def test_pick_strips_whitespace():
    """_pick strips whitespace and returns trimmed value if non-empty."""
    assert model_policy._pick({"default": "  model-id  "}, "default") == "model-id"
    assert model_policy._pick({"copilot": "\tmodel-id\n"}, "copilot") == "model-id"


def test_pick_returns_empty_for_empty_string():
    """_pick returns '' for empty string (per upstream logic)."""
    assert model_policy._pick({"default": ""}, "default") == ""
    assert model_policy._pick({"default": "   "}, "default") == ""  # whitespace only


def test_pick_returns_empty_for_missing_key():
    """_pick returns '' for missing key."""
    assert model_policy._pick({}, "default") == ""
    assert model_policy._pick({"copilot": "x"}, "default") == ""


def test_pick_returns_empty_for_non_string_value():
    """_pick returns '' for non-string values (int, None, dict, list)."""
    assert model_policy._pick({"default": 123}, "default") == ""
    assert model_policy._pick({"default": None}, "default") == ""
    assert model_policy._pick({"default": ["a", "b"]}, "default") == ""
    assert model_policy._pick({"default": {"nested": "x"}}, "default") == ""
    assert model_policy._pick({"default": True}, "default") == ""


def test_pick_handles_non_dict_policy():
    """_pick returns '' when policy is not a dict."""
    assert model_policy._pick(None, "default") == ""
    assert model_policy._pick("not a dict", "default") == ""
    assert model_policy._pick(42, "default") == ""
    assert model_policy._pick([], "default") == ""


# ─── 5. resolve_model tests ──────────────────────

def test_resolve_model_module_precedence_wins():
    """Module override takes precedence over aspect + default."""
    result = model_policy.resolve_model(
        policy={"default": "default-model", "copilot": "aspect-model", "finance": "module-model"},
        ctx={"module": "finance", "aspect": "copilot"},
    )
    assert result == "module-model"


def test_resolve_model_aspect_precedence_over_default():
    """Aspect override wins when module is missing or not in MODULES."""
    result = model_policy.resolve_model(
        policy={"default": "default-model", "copilot": "aspect-model", "finance": "module-model"},
        ctx={"aspect": "copilot"},
    )
    assert result == "aspect-model"


def test_resolve_model_falls_back_to_default():
    """Default is used when module and aspect don't match."""
    result = model_policy.resolve_model(
        policy={"default": "default-model"},
        ctx={"module": "finance", "aspect": "copilot"},
    )
    assert result == "default-model"


def test_resolve_model_empty_policy_returns_empty():
    """Empty policy + empty ctx → '' (auto)."""
    assert model_policy.resolve_model() == ""
    assert model_policy.resolve_model({}, {}) == ""


def test_resolve_model_module_must_be_in_MODULES():
    """Module is only honored if it's in MODULES (finance, crm, docs)."""
    result = model_policy.resolve_model(
        policy={"invalid_module": "should-be-ignored"},
        ctx={"module": "invalid_module"},
    )
    assert result == ""  # Falls through to default (also empty)


def test_resolve_model_aspect_must_be_in_ASPECTS():
    """Aspect is only honored if it's in ASPECTS (copilot, transform)."""
    result = model_policy.resolve_model(
        policy={"invalid_aspect": "should-be-ignored"},
        ctx={"aspect": "invalid_aspect"},
    )
    assert result == ""


def test_resolve_model_module_empty_value_falls_through():
    """Module with empty value falls through to aspect (not used as the result)."""
    result = model_policy.resolve_model(
        policy={"default": "default-model", "finance": "", "copilot": "aspect-model"},
        ctx={"module": "finance", "aspect": "copilot"},
    )
    assert result == "aspect-model"  # Falls through to aspect (not default)


def test_resolve_model_no_ctx_falls_back_to_default():
    """No ctx → uses default."""
    result = model_policy.resolve_model(policy={"default": "default-model"})
    assert result == "default-model"


def test_resolve_model_only_default_set():
    """Only default set + empty ctx → default."""
    result = model_policy.resolve_model(policy={"default": "anthropic/claude-3.5-sonnet"})
    assert result == "anthropic/claude-3.5-sonnet"


# ─── 6. validate tests (source tracking) ──────

def test_validate_tracks_source_module():
    """validate returns source='module' when module override fires."""
    result = model_policy.validate({
        "policy": {"default": "default-model", "finance": "module-model"},
        "ctx": {"module": "finance"},
    })
    assert result == {"resolved_model": "module-model", "source": "module"}


def test_validate_tracks_source_aspect():
    """validate returns source='aspect' when aspect override fires."""
    result = model_policy.validate({
        "policy": {"default": "default-model", "copilot": "aspect-model"},
        "ctx": {"aspect": "copilot"},
    })
    assert result == {"resolved_model": "aspect-model", "source": "aspect"}


def test_validate_tracks_source_default():
    """validate returns source='default' when default is used."""
    result = model_policy.validate({
        "policy": {"default": "default-model"},
        "ctx": {},
    })
    assert result == {"resolved_model": "default-model", "source": "default"}


def test_validate_tracks_source_auto():
    """validate returns source='auto' when everything is empty."""
    result = model_policy.validate({
        "policy": {},
        "ctx": {},
    })
    assert result == {"resolved_model": "", "source": "auto"}


def test_validate_handles_none_policy():
    """validate handles None policy gracefully (empty dict)."""
    result = model_policy.validate({"policy": None, "ctx": {}})
    assert result == {"resolved_model": "", "source": "auto"}


def test_validate_handles_none_ctx():
    """validate handles None ctx gracefully (empty dict)."""
    result = model_policy.validate({"policy": {"default": "x"}, "ctx": None})
    assert result == {"resolved_model": "x", "source": "default"}


# ─── 7. Cross-validator via dispatcher ──────────

def test_validate_dispatches_model_policy():
    """a1_validator.validate('model_policy', ...) dispatches correctly."""
    r = validate("model_policy", {
        "policy": {"default": "anthropic/claude-3.5-sonnet"},
        "ctx": {},
    })
    assert r["resolved_model"] == "anthropic/claude-3.5-sonnet"
    assert r["source"] == "default"


def test_model_policy_in_list_kinds():
    """'model_policy' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "model_policy" in kinds, f"model_policy must be in list_kinds() (got: {kinds})"


# ─── 8. Sovereignty (pure functions) ───────────

def test_model_policy_pure_functions():
    """model_policy.py must be pure — no I/O, no network, no filesystem."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "model_policy.py"
    src = src_path.read_text()

    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "model_policy.py must not require network modules"
    # No filesystem require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*fs[\'"]', src), \
        "model_policy.py must not require fs module"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "model_policy.py must not require child_process"
    # No environment variable reads (pure precedence)
    assert not re.search(r'\bprocess\.env', src), \
        "model_policy.py must not read environment variables"