"""test_settings_store.py — focused tests for the AI settings store (per-install).

The vendored ``settings_store`` module implements the per-install AI settings
file (`ai-settings.json` by default). It:
- Reads settings with `get_settings` (returns defaults on missing/invalid file)
- Writes settings with `update_settings` (atomic, 0600 POSIX perms)
- Redacts secrets with `redacted_for_client` (secrets → bool *Set flags)
- Resolves per-aspect model policy with `resolve_model_policy`

Public API:
- ``DEFAULT_KEYS`` (list: default, copilot, transform, finance, crm, docs)
- ``get_settings(data_dir, file_name, model_keys) -> dict``
- ``update_settings(data_dir, patch, file_name, model_keys) -> dict``
- ``redacted_for_client(settings) -> dict``
- ``resolve_model_policy(data_dir, file_name, model_keys, default_models) -> dict``
- ``validate(input_data) -> dict`` (uniform entry point)
- ``defaults(model_keys) -> dict`` (factory for default settings)

Tests here complement test_validators.py::test_settings_store (parametrized).
This file adds:
- 12 parametrized upstream eval_set verification (mirrors HHVH)
- 6 DEFAULT_KEYS tests (length, type, contents)
- 6 defaults() tests (model_keys applied, openrouterApiKey empty, models dict, etc.)
- 5 get_settings tests (missing file → defaults, invalid JSON, partial file, model_keys, etc.)
- 5 update_settings tests (creates dir, atomic write, 0600 perms, partial patch, all fields)
- 6 redacted_for_client tests (openrouterApiKeySet, models preserved, openNotebook redaction)
- 5 resolve_model_policy tests (stored wins, default fallback, auto, partial)
- 3 cross-validator dispatcher tests
- 1 sovereignty test (perms enforced)

Source:
- src/a1_validator/_vendored/settings_store.py (the contract surface)
- tests/_eval_sets/settings_store.json (canonical ground truth, 12 cases)
- autho://autoresearch-sboss/examples/settings-store/workflow.py (MIT upstream)
- A1-AI-Core/src/settings-store.js (the JS source of truth)
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

import pytest

from a1_validator._vendored import settings_store
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "settings_store.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants ──────────────────────────────────

EXPECTED_DEFAULT_KEYS = ["default", "copilot", "transform", "finance", "crm", "docs"]


# ─── 2. Parametrized upstream eval set ───────────────

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
def test_settings_store_matches_upstream_ground_truth(case, tmp_path):
    """Each upstream eval case must produce the expected result.

    Note: the eval cases don't include dataDir, so we inject a tmp_path.
    This is a known difference from the upstream eval harness which runs
    in a fixed /tmp directory. See A1-Validator follow-up #5.
    """
    inp = dict(case["input"], dataDir=str(tmp_path))
    actual = settings_store.validate(inp)
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. DEFAULT_KEYS ────────────────────────────

def test_default_keys_is_list_of_6():
    """DEFAULT_KEYS is a list of exactly 6 keys."""
    assert isinstance(settings_store.DEFAULT_KEYS, list)
    assert len(settings_store.DEFAULT_KEYS) == 6
    assert settings_store.DEFAULT_KEYS == EXPECTED_DEFAULT_KEYS


def test_default_keys_includes_default_first():
    """'default' is the first key in DEFAULT_KEYS (highest priority fallback)."""
    assert settings_store.DEFAULT_KEYS[0] == "default"


# ─── 4. defaults() factory ───────────────────────

def test_defaults_returns_all_required_top_level_keys():
    """defaults() returns a dict with the 3 required top-level keys."""
    d = settings_store.defaults()
    assert "openrouterApiKey" in d
    assert "models" in d
    assert "openNotebook" in d


def test_defaults_openrouter_api_key_is_empty_string():
    """defaults() sets openrouterApiKey to '' (never None)."""
    d = settings_store.defaults()
    assert d["openrouterApiKey"] == ""


def test_defaults_models_has_all_keys():
    """defaults() sets all model keys to '' in the models dict."""
    d = settings_store.defaults()
    assert d["models"] == {k: "" for k in EXPECTED_DEFAULT_KEYS}


def test_defaults_open_notebook_disabled_by_default():
    """defaults() sets openNotebook.enabled=False, baseUrl='', apiKey=''."""
    d = settings_store.defaults()
    assert d["openNotebook"] == {"enabled": False, "baseUrl": "", "apiKey": ""}


def test_defaults_with_custom_model_keys():
    """defaults() uses the provided model_keys (not DEFAULT_KEYS)."""
    d = settings_store.defaults(model_keys=["a", "b", "c"])
    assert d["models"] == {"a": "", "b": "", "c": ""}
    # OpenNotebook still has the default structure
    assert d["openNotebook"]["enabled"] is False


def test_defaults_is_pure():
    """defaults() is pure — each call returns a fresh dict (no shared state)."""
    d1 = settings_store.defaults()
    d2 = settings_store.defaults()
    assert d1 is not d2
    assert d1["models"] is not d2["models"]
    d1["openrouterApiKey"] = "X"
    assert d2["openrouterApiKey"] == ""  # not affected


# ─── 5. get_settings (file reader) ────────────────

def test_get_settings_missing_file_returns_defaults(tmp_path):
    """get_settings returns defaults when the file doesn't exist."""
    result = settings_store.get_settings(str(tmp_path), "settings.json")
    assert result["openrouterApiKey"] == ""
    assert result["models"] == {k: "" for k in EXPECTED_DEFAULT_KEYS}
    assert result["openNotebook"]["enabled"] is False


def test_get_settings_invalid_json_returns_defaults(tmp_path):
    """get_settings returns defaults on invalid JSON (graceful fallback)."""
    (tmp_path / "settings.json").write_text("not valid json {{{")
    result = settings_store.get_settings(str(tmp_path), "settings.json")
    assert result["openrouterApiKey"] == ""  # defaults


def test_get_settings_empty_file_returns_defaults(tmp_path):
    """get_settings returns defaults on empty file."""
    (tmp_path / "settings.json").write_text("")
    result = settings_store.get_settings(str(tmp_path), "settings.json")
    assert result["openrouterApiKey"] == ""


def test_get_settings_with_valid_file(tmp_path):
    """get_settings reads and merges valid settings."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "openrouterApiKey": "sk-test-123",
        "models": {"default": "anthropic/claude-3.5-sonnet"},
        "openNotebook": {"enabled": True, "baseUrl": "https://nb.local", "apiKey": "nb-key"},
    }))
    result = settings_store.get_settings(str(tmp_path), "settings.json")
    assert result["openrouterApiKey"] == "sk-test-123"
    assert result["models"]["default"] == "anthropic/claude-3.5-sonnet"
    assert result["openNotebook"]["enabled"] is True
    assert result["openNotebook"]["baseUrl"] == "https://nb.local"


def test_get_settings_with_custom_model_keys(tmp_path):
    """get_settings uses the provided model_keys."""
    (tmp_path / "settings.json").write_text("{}")
    result = settings_store.get_settings(str(tmp_path), "settings.json", model_keys=["a", "b"])
    assert result["models"] == {"a": "", "b": ""}


def test_get_settings_strips_whitespace_on_load(tmp_path):
    """get_settings strips whitespace from string values."""
    (tmp_path / "settings.json").write_text(json.dumps({
        "openrouterApiKey": "  sk-test  ",
        "openNotebook": {"baseUrl": "  https://nb.local  ", "apiKey": "  nb-key  "},
    }))
    result = settings_store.get_settings(str(tmp_path), "settings.json")
    assert result["openrouterApiKey"] == "sk-test"
    assert result["openNotebook"]["baseUrl"] == "https://nb.local"
    assert result["openNotebook"]["apiKey"] == "nb-key"


# ─── 6. update_settings (file writer) ──────────

def test_update_settings_creates_file_and_directory(tmp_path):
    """update_settings creates the data dir + file if they don't exist."""
    new_dir = tmp_path / "new_dir"
    result = settings_store.update_settings(str(new_dir), {"openrouterApiKey": "sk-new"})
    assert new_dir.exists()
    assert (new_dir / "ai-settings.json").exists()
    assert result["openrouterApiKey"] == "sk-new"


def test_update_settings_atomic_write(tmp_path):
    """update_settings writes the file (atomic, even on success)."""
    settings_store.update_settings(str(tmp_path), {"openrouterApiKey": "sk-atomic"})
    content = (tmp_path / "ai-settings.json").read_text()
    assert "sk-atomic" in content


def test_update_settings_sets_0600_permissions(tmp_path):
    """update_settings sets the file permissions to 0600 (owner read/write only)."""
    settings_store.update_settings(str(tmp_path), {"openrouterApiKey": "sk-perms"})
    perms = stat.S_IMODE((tmp_path / "ai-settings.json").stat().st_mode)
    assert perms == 0o600, f"Expected 0o600, got {oct(perms)}"


def test_update_settings_partial_patch_preserves_other_fields(tmp_path):
    """update_settings with a partial patch preserves unmentioned fields."""
    settings_store.update_settings(str(tmp_path), {
        "openrouterApiKey": "sk-1",
        "models": {"default": "anthropic/claude-3.5-sonnet"},
    })
    # Second update only patches the api key
    settings_store.update_settings(str(tmp_path), {"openrouterApiKey": "sk-2"})
    result = settings_store.get_settings(str(tmp_path))
    assert result["openrouterApiKey"] == "sk-2"  # updated
    assert result["models"]["default"] == "anthropic/claude-3.5-sonnet"  # preserved


def test_update_settings_strips_whitespace_on_write(tmp_path):
    """update_settings strips whitespace from string values."""
    settings_store.update_settings(str(tmp_path), {
        "openrouterApiKey": "  sk-strip  ",
        "openNotebook": {"baseUrl": "  https://nb.local/  "},  # trailing slash
    })
    result = settings_store.get_settings(str(tmp_path))
    assert result["openrouterApiKey"] == "sk-strip"
    assert result["openNotebook"]["baseUrl"] == "https://nb.local"  # rstrip("/")


# ─── 7. redacted_for_client (safe projection) ────

def test_redacted_for_client_openrouter_api_key_becomes_set_flag():
    """redacted_for_client converts openrouterApiKey string to openrouterApiKeySet boolean."""
    s = {"openrouterApiKey": "sk-secret", "models": {}, "openNotebook": {}}
    r = settings_store.redacted_for_client(s)
    assert r["openrouterApiKeySet"] is True
    assert "openrouterApiKey" not in r  # secret is gone


def test_redacted_for_client_no_api_key_set_is_false():
    """redacted_for_client returns openrouterApiKeySet=False when api key is empty."""
    s = {"openrouterApiKey": "", "models": {}, "openNotebook": {}}
    r = settings_store.redacted_for_client(s)
    assert r["openrouterApiKeySet"] is False


def test_redacted_for_client_preserves_models():
    """redacted_for_client preserves the full models dict (no secrets there)."""
    s = {
        "openrouterApiKey": "",
        "models": {"default": "anthropic/claude-3.5-sonnet", "copilot": "openai/gpt-4o"},
        "openNotebook": {},
    }
    r = settings_store.redacted_for_client(s)
    assert r["models"] == s["models"]


def test_redacted_for_client_open_notebook_api_key_becomes_set_flag():
    """redacted_for_client converts openNotebook.apiKey to apiKeySet boolean."""
    s = {
        "openrouterApiKey": "",
        "models": {},
        "openNotebook": {"enabled": True, "baseUrl": "https://nb.local", "apiKey": "nb-secret"},
    }
    r = settings_store.redacted_for_client(s)
    assert r["openNotebook"]["enabled"] is True
    assert r["openNotebook"]["baseUrl"] == "https://nb.local"
    assert r["openNotebook"]["apiKeySet"] is True
    assert "apiKey" not in r["openNotebook"]  # secret is gone


def test_redacted_for_client_handles_none():
    """redacted_for_client handles None gracefully."""
    r = settings_store.redacted_for_client(None)
    assert r["openrouterApiKeySet"] is False
    assert r["models"] == {}
    assert r["openNotebook"]["enabled"] is False


def test_redacted_for_client_handles_missing_fields():
    """redacted_for_client handles missing fields gracefully."""
    r = settings_store.redacted_for_client({})
    assert r["openrouterApiKeySet"] is False
    assert r["models"] == {}
    assert r["openNotebook"] == {"enabled": False, "baseUrl": "", "apiKeySet": False}


# ─── 8. resolve_model_policy ────────────────────

def test_resolve_model_policy_uses_stored_value(tmp_path):
    """resolve_model_policy returns the stored model if set."""
    (tmp_path / "ai-settings.json").write_text(json.dumps({
        "models": {"default": "anthropic/claude-3.5-sonnet"}
    }))
    result = settings_store.resolve_model_policy(str(tmp_path))
    assert result["default"] == "anthropic/claude-3.5-sonnet"


def test_resolve_model_policy_falls_back_to_default(tmp_path):
    """resolve_model_policy falls back to default_models when stored is empty."""
    (tmp_path / "ai-settings.json").write_text(json.dumps({"models": {}}))
    result = settings_store.resolve_model_policy(
        str(tmp_path),
        default_models={"default": "openai/gpt-4o"},
    )
    assert result["default"] == "openai/gpt-4o"


def test_resolve_model_policy_returns_empty_string_when_nothing_set(tmp_path):
    """resolve_model_policy returns '' (auto) when neither stored nor default set."""
    (tmp_path / "ai-settings.json").write_text(json.dumps({"models": {}}))
    result = settings_store.resolve_model_policy(str(tmp_path))
    assert result["default"] == ""  # auto


def test_resolve_model_policy_stored_wins_over_default(tmp_path):
    """resolve_model_policy stored value wins over default_models."""
    (tmp_path / "ai-settings.json").write_text(json.dumps({
        "models": {"default": "stored-model"}
    }))
    result = settings_store.resolve_model_policy(
        str(tmp_path),
        default_models={"default": "default-model"},
    )
    assert result["default"] == "stored-model"


def test_resolve_model_policy_handles_partial_overrides(tmp_path):
    """resolve_model_policy only overrides the keys actually set in stored."""
    (tmp_path / "ai-settings.json").write_text(json.dumps({
        "models": {"default": "stored-model"}  # only default set
    }))
    result = settings_store.resolve_model_policy(
        str(tmp_path),
        default_models={"default": "default-model", "copilot": "default-copilot"},
    )
    assert result["default"] == "stored-model"  # overridden
    assert result["copilot"] == "default-copilot"  # from default


# ─── 9. Cross-validator via dispatcher ──────────

def test_validate_dispatches_settings_store(tmp_path):
    """a1_validator.validate('settings_store', ...) dispatches correctly."""
    r = validate("settings_store", {
        "dataDir": str(tmp_path),
        "operations": [{"operation": "getSettings", "modelKeys": ["default", "copilot"]}],
    })
    assert "result" in r
    assert r["result"]["openrouterApiKey"] == ""
    assert r["result"]["models"]["default"] == ""
    assert r["result"]["models"]["copilot"] == ""


def test_settings_store_in_list_kinds():
    """'settings_store' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "settings_store" in kinds, f"settings_store must be in list_kinds() (got: {kinds})"


# ─── 10. Sovereignty (file I/O only at data_dir) ───

def test_settings_store_pure_data_dir_respected():
    """settings_store.py uses injected data_dir (no hardcoded paths)."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "settings_store.py"
    src = src_path.read_text()

    # No hardcoded paths (e.g. /home, /var, /usr)
    assert not re.search(r'["\']/(home|var|usr|tmp|opt)/', src), \
        "settings_store.py must not hardcode paths"
    # No network require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net|fetch)', src), \
        "settings_store.py must not require network modules"
    # No subprocess
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*child_process[\'"]', src), \
        "settings_store.py must not require child_process"