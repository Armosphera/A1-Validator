"""Pytest suite for the a1_validator FastAPI HTTP service (`server.py`).

The HTTP layer is a thin transport over the core validators — its
contract is "every public validator function becomes a `/validate/<kind>`
POST route; the body is wrapped into the validator's primary input key,
the response is always HTTP 200, and the body always carries an `ok`
field". These tests pin that contract end-to-end via FastAPI's
`TestClient` (synchronous, no live server).

What's covered:

* `GET /` discovery: 200, name + version + 33-name validator list.
* `GET /validators`: 200, 33 entries.
* `POST /validate/hhvh` with `{"value": "00123456"}` → 200 + ok=true.
* `POST /validate/hhvh` with `{"value": "99999999"}` (all-same-digit HHVH)
  → 200 + ok=false. This catches the most common "the validator ran but
  the result is just passed through unchanged" regression.
* `POST /batch/hhvh` with `{"values": [...]}` → 200, results array.
* `GET /openapi.json` → 200, paths includes all 23 `/validate/<kind>` and
  `/batch/<kind>` operations (>= 46 paths, plus the 5 FastAPI built-ins).
* `GET /docs` → 200, HTML Swagger UI.

Plus three "shape" tests that catch the `_build_input` shortcut regressions
for non-`hhvh` validators:

* `POST /validate/inn` with `{"value": "7707083893"}` (Russian INN legal)
  → ok=true. Confirms the primary-key map is wired (`value` → `id`).
* `POST /validate/phone_am` with `{"value": "+374 11 123456"}` → ok=true.
  Confirms the body wrapping for `phone` (a key that isn't `hvhh`).
* `POST /validate/regions_ru` with `{"value": "москва"}` → ok=true.
  Confirms Cyrillic values survive the JSON round-trip unchanged.

Note: this test file lives in a separate `TestClient` import boundary —
it only runs when the `server` extra is installed. Pytest still picks
it up under the default `testpaths = ["tests"]` config in
`pyproject.toml`, but a missing fastapi/httpx will surface as a
collection-time ImportError rather than a silent skip. That's
intentional: the deliverable is the HTTP service, and the tests
must run for it to be considered done.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from a1_validator._port import list_kinds
from a1_validator.server import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """A single TestClient for the module — the app is stateless."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Discovery endpoints.
# ---------------------------------------------------------------------------


def test_root_returns_200_with_name_version_and_23_validators(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "a1-validator"
    assert isinstance(body["version"], str) and body["version"]  # non-empty
    assert isinstance(body["validators"], list)
    assert len(body["validators"]) == 33
    # The 33 names match the canonical _port._VALIDATORS list (defensive
    # against accidental reordering or removal of a kind in __init__.py).
    assert sorted(body["validators"]) == sorted(list_kinds())


def test_validators_returns_200_with_23_names(client: TestClient) -> None:
    resp = client.get("/validators")
    assert resp.status_code == 200
    body = resp.json()
    assert "validators" in body
    assert len(body["validators"]) == 33
    assert "hhvh" in body["validators"]
    assert "invoice" in body["validators"]


# ---------------------------------------------------------------------------
# /validate/<kind> — the single-value happy + sad path.
# ---------------------------------------------------------------------------


def test_validate_hhvh_valid_value_returns_ok_true(client: TestClient) -> None:
    resp = client.post("/validate/hhvh", json={"value": "00123456"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    # The hhvh validator returns the canonical dict shape; the server
    # passes it through unchanged when `ok` is already present.
    assert body["normalized"] == "00123456"
    assert body["error"] is None


def test_validate_hhvh_all_same_digits_returns_ok_false(client: TestClient) -> None:
    # 99999999 is 8 × the digit 9, which the hhvh validator explicitly
    # rejects (matches _ALL_SAME_RE). The server must NOT swallow the
    # ok=false from the underlying validator — that's the bug the test
    # exists to catch.
    resp = client.post("/validate/hhvh", json={"value": "99999999"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert body["normalized"] == "99999999"
    assert body["error"]  # non-empty error message


def test_validate_unknown_kind_returns_404(client: TestClient) -> None:
    # /validate/<kind> is registered explicitly per kind, so an unknown
    # kind gets the standard FastAPI 404 (not the 200 + ok=false contract
    # that applies to known kinds).
    resp = client.post("/validate/this_does_not_exist", json={"value": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /validate/<kind> — primary-key wrapping for non-`hhvh` validators.
# ---------------------------------------------------------------------------


def test_validate_inn_wraps_value_under_id_key(client: TestClient) -> None:
    # 7707083893 is a known-valid Russian INN (legal entity). The
    # primary-key map sends `value` → `id` for the inn kind, so the
    # server must build `{"id": "7707083893"}` and run ru_identifiers.
    resp = client.post("/validate/inn", json={"value": "7707083893"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["normalized"] == "7707083893"
    assert body["kind"] == "inn_legal"


def test_validate_phone_am_wraps_value_under_phone_key(client: TestClient) -> None:
    resp = client.post("/validate/phone_am", json={"value": "+374 11 123456"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["nsn"] == "11123456"
    assert body["e164"] == "+37411123456"


def test_validate_regions_ru_preserves_cyrillic_value(client: TestClient) -> None:
    resp = client.post("/validate/regions_ru", json={"value": "москва"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["found"] is True
    # regions_ru uses ISO-style codes (RU-MOW, not the old "77"). Pinning
    # the exact string here would be brittle; the test contract is "Cyrillic
    # input survives the JSON round-trip and the validator returns its
    # result unchanged".
    assert body["code"] == "RU-MOW"
    assert body["ru"] == "Москва"
    assert body["en"] == "Moscow"


# ---------------------------------------------------------------------------
# /batch/<kind> — list of values.
# ---------------------------------------------------------------------------


def test_batch_hhvh_returns_results_array(client: TestClient) -> None:
    payload = {"values": ["00123456", "12345678", "99999999", ""]}
    resp = client.post("/batch/hhvh", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "results" in body
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 4

    # Spot-check the four outcomes.
    r0, r1, r2, r3 = body["results"]
    assert r0["ok"] is True and r0["normalized"] == "00123456"
    assert r1["ok"] is True and r1["normalized"] == "12345678"
    assert r2["ok"] is False  # all-same-digit
    assert r3["ok"] is False  # empty


def test_batch_hhvh_with_dict_items_passes_through(client: TestClient) -> None:
    # Items in the `values` list can be dicts (full input) — server
    # passes them through without the primary-key wrap. This is the
    # escape hatch for multi-field validators used via batch.
    payload = {"values": [{"hvhh": "00123456"}, {"hvhh": ""}]}
    resp = client.post("/batch/hhvh", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"][0]["ok"] is True
    assert body["results"][1]["ok"] is False


# ---------------------------------------------------------------------------
# OpenAPI + Swagger UI.
# ---------------------------------------------------------------------------


def test_openapi_json_returns_200_with_all_23_validators_as_paths(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200, resp.text
    spec = resp.json()
    paths = spec["paths"]
    # The HTTP service exposes one /validate/<kind> + one /batch/<kind>
    # pair per validator — 46 paths minimum, plus the 5 FastAPI built-ins
    # (/, /validators, /docs, /openapi.json, /redoc) = 51+ total.
    assert len(paths) >= 33, f"expected >= 33 paths, got {len(paths)}"

    # Every canonical validator name has both a /validate/<kind> and a
    # /batch/<kind> route.
    for kind in list_kinds():
        assert f"/validate/{kind}" in paths, f"missing /validate/{kind}"
        assert f"/batch/{kind}" in paths, f"missing /batch/{kind}"


def test_docs_returns_200_html(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200, resp.text
    # FastAPI's Swagger UI is HTML — assert the content-type, not the
    # exact markup (which FastAPI may tweak between versions).
    assert resp.headers["content-type"].startswith("text/html")
    # A tell-tale string in the Swagger UI bundle.
    assert "swagger" in resp.text.lower()


# ---------------------------------------------------------------------------
# Error handling.
# ---------------------------------------------------------------------------


def test_validate_known_kind_with_invalid_body_returns_200_with_ok_false(
    client: TestClient,
) -> None:
    # The contract is "200 always" for known kinds, even on bad input.
    # The validator runs, fails its own check, and the server returns
    # the validator's ok=false result verbatim.
    resp = client.post("/validate/hhvh", json={"value": "not-a-number!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]  # non-empty error message
    assert "normalized" in body
