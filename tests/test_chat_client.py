"""test_chat_client.py — focused tests for the AI chat proxy (OpenRouter).

The vendored ``chat_client`` module implements the OpenRouter chat-completions
proxy used by every A1 product to call LLMs. It uses dependency injection
for the egress-gated `safeFetch` (consumer's allowlist, not @a1/ai's).

Public API:
- ``create_chat_client(safe_fetch, openrouter, max_output_tokens=1200) -> ChatClient``
- ``ChatClient.call_model(instructions, input, model, api_key, env, max_tokens) -> dict``
- ``ChatClient.call_vision(instructions, input, image_base64, mime_type, ...) -> dict``
- ``ChatClient.call_structured(instructions, input, schema, schema_name, strict, ...) -> dict``
- ``HttpError(status_code, code, message)`` — raised on AI errors
- ``_extract_text(payload)`` — extract text from OpenRouter response
- ``validate(input_data)`` — uniform entry point (mirrors others)

Per-request contract:
- Returns ``{text, responseId, usage, provider, model}``
- All HTTP goes through the injected ``safe_fetch`` (never raw `requests`/`httpx`)
- API key required (else 503 AI_NOT_CONFIGURED)
- Provider is "openrouter" (single cloud aggregator, per upstream pattern)

Tests here complement test_validators.py::test_chat_client (parametrized
verification against the eval_set). This file adds:
- 12 parametrized upstream eval_set verification (mirrors HHVH)
- 3 known-real fixtures (system+user message, max_tokens, responseId)
- 3 HttpError cases (no API key, error response, bad JSON)
- 3 call_vision cases (image_base64, mime_type, text+image)
- 3 call_structured cases (JSON schema, response_format, schema_name)
- 4 _extract_text tests (happy path, missing key, content not string, empty)
- 3 cross-validator dispatcher tests
- 1 sovereignty test (no raw HTTP)

Source:
- src/a1_validator/_vendored/chat_client.py (the contract surface)
- tests/_eval_sets/chat_client.json (canonical ground truth, 12 cases)
- autho://autoresearch-sboss/examples/chat-client/workflow.py (MIT upstream)
- OpenRouter API spec (chat-completions endpoint)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from a1_validator._vendored import chat_client
from a1_validator import validate, list_kinds


# Load upstream eval_set (ground truth corpus)
EVAL_SET_PATH = Path(__file__).resolve().parent / "_eval_sets" / "chat_client.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text()) if EVAL_SET_PATH.exists() else []


# ─── 1. Constants (per OpenRouter API spec) ────────────────

DEFAULT_MAX_OUTPUT_TOKENS = 1200
EXPECTED_ENDPOINT_SUFFIX = "/chat/completions"
EXPECTED_PROVIDER = "openrouter"


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
def test_chat_client_matches_upstream_ground_truth(case):
    """Each upstream eval case must produce the expected result.

    Mirrors test_validators.py matching contract:
    - Subset equality (extra keys in actual are OK)
    - Dotted-path keys (e.g. 'last_request.method' → actual['last_request']['method'])
    """
    actual = chat_client.validate(case["input"])
    expected = case["expected"]
    for key, value in expected.items():
        actual_value = _dotted_get(actual, key)
        assert actual_value == value, (
            f"case {case['input']}: key {key} — expected {value!r}, got {actual_value!r}"
        )


# ─── 3. create_chat_client (factory) ─────────────────────

def _make_mock_safe_fetch(response, status=200, ok=True, throw_on_call=False):
    """Build a mock safeFetch that records calls + returns canned response."""
    call_log = {"url": None, "options": None, "env": None}

    def safe_fetch(url, options, env):
        call_log["url"] = url
        call_log["options"] = options
        call_log["env"] = env
        if throw_on_call:
            raise RuntimeError("network down")
        return {"ok": ok, "status": status, "json": lambda: response}

    return safe_fetch, call_log


def _make_client(max_output_tokens=1200, baseUrl="https://openrouter.ai/api/v1"):
    """Build a ChatClient with a mock safeFetch."""
    safe_fetch, call_log = _make_mock_safe_fetch(
        {"id": "resp-1", "choices": [{"message": {"content": "hello"}}], "model": "gpt-4"},
    )
    client = chat_client.create_chat_client(
        safe_fetch,
        {"baseUrl": baseUrl, "referer": "https://a1.local", "title": "A1"},
        max_output_tokens,
    )
    return client, call_log


def test_create_chat_client_with_valid_inputs():
    """create_chat_client succeeds with valid safe_fetch + openrouter config."""
    client, _ = _make_client()
    assert client is not None
    assert client.endpoint == "https://openrouter.ai/api/v1/chat/completions"
    assert client._max_output_tokens == 1200


def test_create_chat_client_rejects_non_callable_safe_fetch():
    """create_chat_client raises TypeError if safe_fetch is not callable."""
    with pytest.raises(TypeError) as exc_info:
        chat_client.create_chat_client(
            "not a function",
            {"baseUrl": "https://openrouter.ai/api/v1"},
        )
    assert "safe_fetch" in str(exc_info.value).lower()


def test_create_chat_client_rejects_missing_baseurl():
    """create_chat_client raises TypeError if openrouter.baseUrl is missing."""
    with pytest.raises(TypeError) as exc_info:
        chat_client.create_chat_client(
            _make_mock_safe_fetch(None)[0],
            {"referer": "x", "title": "y"},  # no baseUrl
        )
    assert "baseurl" in str(exc_info.value).lower()


def test_create_chat_client_strips_trailing_slash_from_baseurl():
    """create_chat_client normalizes baseUrl (strips trailing slashes)."""
    safe_fetch, _ = _make_mock_safe_fetch(None)
    client = chat_client.create_chat_client(
        safe_fetch,
        {"baseUrl": "https://openrouter.ai/api/v1///"},
    )
    assert client.endpoint == "https://openrouter.ai/api/v1/chat/completions"


# ─── 4. ChatClient.call_model ─────────────────────────

def test_call_model_returns_text_responseId_usage_provider_model():
    """call_model returns the 5 expected fields."""
    client, call_log = _make_client()
    result = client.call_model(
        instructions="You are a helper.",
        input="Hello",
        model="gpt-4",
        api_key="sk-test",
        env={"OPENROUTER_API_KEY": "sk-test"},
    )
    assert result["text"] == "hello"
    assert result["responseId"] == "resp-1"
    assert result["usage"] is None  # not in canned response
    assert result["provider"] == EXPECTED_PROVIDER
    assert result["model"] == "gpt-4"


def test_call_model_uses_safe_fetch_with_correct_endpoint():
    """call_model routes through safe_fetch with the right endpoint."""
    client, call_log = _make_client()
    client.call_model(
        instructions="",
        input="hi",
        model="gpt-4",
        api_key="sk-test",
        env={},
    )
    assert call_log["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call_log["options"]["method"] == "POST"
    assert call_log["options"]["headers"]["Authorization"] == "Bearer sk-test"
    assert "Content-Type" in call_log["options"]["headers"]


def test_call_model_no_api_key_raises_503():
    """call_model without api_key raises HttpError(503, AI_NOT_CONFIGURED)."""
    client, _ = _make_client()
    with pytest.raises(chat_client.HttpError) as exc_info:
        client.call_model(input="hi", model="gpt-4", api_key="", env={})
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "AI_NOT_CONFIGURED"


def test_call_model_400_error_raises_http_error():
    """call_model on 400 response raises HttpError with API error code."""
    safe_fetch, _ = _make_mock_safe_fetch(
        {"error": {"code": "INVALID_API_KEY", "message": "Bad key"}},
        status=400, ok=False,
    )
    client = chat_client.create_chat_client(
        safe_fetch, {"baseUrl": "https://openrouter.ai/api/v1"},
    )
    with pytest.raises(chat_client.HttpError) as exc_info:
        client.call_model(input="hi", model="gpt-4", api_key="sk-test", env={})
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_API_KEY"
    assert "Bad key" in exc_info.value.message


def test_call_model_respects_max_tokens_override():
    """call_model honors the max_tokens argument (overrides default)."""
    client, call_log = _make_client(max_output_tokens=2000)
    client.call_model(input="hi", model="gpt-4", api_key="sk-test", env={}, max_tokens=500)
    body = json.loads(call_log["options"]["body"])
    assert body["max_tokens"] == 500


# ─── 5. ChatClient.call_vision ────────────────────────

def test_call_vision_includes_image_base64_in_user_message():
    """call_vision includes the image as a data URL in the user message."""
    client, call_log = _make_client()
    client.call_vision(
        instructions="",
        input="What's in this image?",
        image_base64="iVBORw0KGgoAAAA==",
        mime_type="image/png",
        model="gpt-4-vision",
        api_key="sk-test",
        env={},
    )
    body = json.loads(call_log["options"]["body"])
    user_msg = body["messages"][-1]
    # User message has 2 parts: text + image_url
    assert isinstance(user_msg["content"], list)
    assert user_msg["content"][0]["type"] == "text"
    assert user_msg["content"][0]["text"] == "What's in this image?"
    assert user_msg["content"][1]["type"] == "image_url"
    assert user_msg["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "iVBORw0KGgoAAAA==" in user_msg["content"][1]["image_url"]["url"]


def test_call_vision_default_mime_type_jpeg():
    """call_vision defaults to image/jpeg if not specified."""
    client, call_log = _make_client()
    client.call_vision(
        instructions="", input="x", image_base64="AAAA",
        model="gpt-4-vision", api_key="sk-test", env={},
        # No mime_type → defaults to image/jpeg
    )
    body = json.loads(call_log["options"]["body"])
    url = body["messages"][-1]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")


def test_call_vision_returns_text_extracted():
    """call_vision returns the extracted text from the response."""
    safe_fetch, _ = _make_mock_safe_fetch(
        {"id": "v1", "choices": [{"message": {"content": "A cat"}}], "model": "gpt-4-vision"},
    )
    client = chat_client.create_chat_client(
        safe_fetch, {"baseUrl": "https://openrouter.ai/api/v1"},
    )
    result = client.call_vision(
        instructions="", input="x", image_base64="AAAA",
        model="gpt-4-vision", api_key="sk-test", env={},
    )
    assert result["text"] == "A cat"
    assert result["responseId"] == "v1"
    assert result["provider"] == EXPECTED_PROVIDER


# ─── 6. ChatClient.call_structured ───────────────────

def test_call_structured_includes_json_schema_in_response_format():
    """call_structured adds response_format with json_schema."""
    # Use a response that IS valid JSON (the structured call will json.loads it)
    safe_fetch, call_log = _make_mock_safe_fetch(
        {"id": "s1", "choices": [{"message": {"content": '{"x": 42}'}}], "model": "gpt-4"},
    )
    client = chat_client.create_chat_client(
        safe_fetch, {"baseUrl": "https://openrouter.ai/api/v1"},
    )
    schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
    client.call_structured(
        instructions="",
        input="Return x=42",
        schema=schema,
        schema_name="result",
        strict=True,
        model="gpt-4",
        api_key="sk-test",
        env={},
    )
    body = json.loads(call_log["options"]["body"])
    assert body["response_format"]["type"] == "json_schema"
    rf_schema = body["response_format"]["json_schema"]
    assert rf_schema["name"] == "result"
    assert rf_schema["strict"] is True
    assert rf_schema["schema"] == schema


def test_call_structured_parses_json_response():
    """call_structured parses the text response as JSON."""
    safe_fetch, _ = _make_mock_safe_fetch(
        {"id": "s1", "choices": [{"message": {"content": '{"x": 42}'}}], "model": "gpt-4"},
    )
    client = chat_client.create_chat_client(
        safe_fetch, {"baseUrl": "https://openrouter.ai/api/v1"},
    )
    result = client.call_structured(
        instructions="", input="x", schema={}, model="gpt-4",
        api_key="sk-test", env={},
    )
    assert result["data"] == {"x": 42}
    assert result["text"] == '{"x": 42}'


def test_call_structured_bad_json_raises_502():
    """call_structured raises 502 AI_BAD_JSON if response is not valid JSON."""
    safe_fetch, _ = _make_mock_safe_fetch(
        {"id": "s1", "choices": [{"message": {"content": "not json"}}], "model": "gpt-4"},
    )
    client = chat_client.create_chat_client(
        safe_fetch, {"baseUrl": "https://openrouter.ai/api/v1"},
    )
    with pytest.raises(chat_client.HttpError) as exc_info:
        client.call_structured(
            instructions="", input="x", schema={}, model="gpt-4",
            api_key="sk-test", env={},
        )
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "AI_BAD_JSON"


# ─── 7. _extract_text helper ──────────────────────────

def test_extract_text_happy_path():
    """_extract_text returns trimmed text from choices[0].message.content."""
    payload = {"choices": [{"message": {"content": "  hello world  "}}]}
    assert chat_client._extract_text(payload) == "hello world"


def test_extract_text_missing_choices_returns_empty():
    """_extract_text returns '' for missing choices."""
    assert chat_client._extract_text({}) == ""
    assert chat_client._extract_text({"choices": []}) == ""
    assert chat_client._extract_text({"choices": [{}]}) == ""


def test_extract_text_content_not_string_returns_empty():
    """_extract_text returns '' if content is not a string."""
    payload = {"choices": [{"message": {"content": ["text", "list"]}}]}
    assert chat_client._extract_text(payload) == ""


def test_extract_text_none_payload_returns_empty():
    """_extract_text returns '' for None payload."""
    assert chat_client._extract_text(None) == ""


# ─── 8. Cross-validator via dispatcher ──────────────

def test_validate_dispatches_chat_client():
    """a1_validator.validate('chat_client', ...) dispatches correctly."""
    r = validate("chat_client", {
        "operation": "callModel",
        "openrouter": {"baseUrl": "https://openrouter.ai/api/v1"},
        "kwargs": {"input": "hi", "model": "gpt-4", "apiKey": "sk-test"},
        "safeFetch_response": {"id": "r1", "choices": [{"message": {"content": "hi back"}}]},
        "safeFetch_status": 200,
        "safeFetch_ok": True,
    })
    assert r["operation"] == "callModel"
    assert r["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"
    # The call happened
    assert _dotted_get(r, "text") == "hi back"


def test_chat_client_in_list_kinds():
    """'chat_client' must be in a1_validator.list_kinds()."""
    kinds = list_kinds()
    assert "chat_client" in kinds, f"chat_client must be in list_kinds() (got: {kinds})"


# ─── 9. Sovereignty (offline-capable) ──────────────

def test_chat_client_pure_functions():
    """chat_client.py must be pure — no raw HTTP, no I/O."""
    import pathlib

    src_path = pathlib.Path(__file__).parent.parent / "src" / "a1_validator" / "_vendored" / "chat_client.py"
    src = src_path.read_text()

    # No raw HTTP module require
    assert not re.search(r'\brequire\s*\(\s*[\'"]\s*(http|https|net)', src), \
        "chat_client.py must not require http/https/net modules"
    # No raw HTTP library (requests, httpx, aiohttp, urllib3, urllib)
    assert not re.search(r'\b(httpx|aiohttp|requests|urllib3)\b', src), \
        "chat_client.py must not use any HTTP library directly"
    # The only fetch must be the injected safe_fetch (check for `self._safe_fetch`)
    assert "self._safe_fetch" in src, \
        "chat_client.py must use self._safe_fetch (injected) for all HTTP calls"
    # No env reads outside the test
    # (chat_client doesn't read env directly — env is injected via call)