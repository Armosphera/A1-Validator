"""server.py — FastAPI app exposing the 23 SBOSS validators as REST endpoints.

The app is deliberately small: one ``GET /`` discovery endpoint, one
``GET /validators`` list endpoint, then 23 explicit ``POST /validate/<kind>``
and 23 ``POST /batch/<kind>`` routes (one pair per public validator name).
The explicit registration — instead of a single ``POST /validate/{kind}``
path-parameter route — keeps the generated OpenAPI schema readable:
consumers see one operation per validator instead of a single ``{kind}``
placeholder.

Every public validator accepts a uniform body shape on ``/validate/<kind>``:

    { "value": "<string>" }                    # single-key validators
    { "value": { "<key>": ... } }              # multi-key validators (full dict)
    { "raw":   { "<key>": ... } }              # explicit passthrough
    { "hvhh":  "00123456", ... }               # body is the input dict as-is

The ``value`` shortcut maps the string to the validator's primary input key
(``hhvh`` → ``hvhh``, ``inn`` → ``id``, ``phone_am`` → ``phone``, …). For
validators that need a full input dict (chat_client, model_catalog,
settings_store, vat_ru, payroll_ru, open_notebook, product_research,
model_policy, einvoice_am, ru_einvoice, vat_return_form, vat_return, …)
pass a dict as ``value`` or as ``raw``, or send the dict at the top level.

The response is always HTTP 200 (the validator may have rejected the input —
that's a successful call with ``ok: false`` in the body). The body always
includes an ``ok`` key. If the validator raised an exception, the body is
``{"ok": false, "error": "<class>: <message>", "input": <body>}``.

Run the service with:

    a1-validate serve --host 0.0.0.0 --port 8000

…or directly with uvicorn:

    uvicorn a1_validator.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

import a1_validator
from a1_validator._port import get_validator, list_kinds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-validator input-key map for the ``{"value": "<string>"}`` shortcut.
#
# These are the validators whose vendored ``validate(input_data)`` reads a
# single primary key out of ``input_data``. A request body of
# ``{"value": "00123456"}`` becomes ``{"hvhh": "00123456"}`` for the hhvh
# validator, ``{"id": "7707083893"}`` for inn, etc.
#
# Validators not in this map require a full input dict — pass it as
# ``{"value": {...}}`` or as the top-level body.
# ---------------------------------------------------------------------------
_VALUE_KEY: dict[str, str] = {
    "hhvh": "hvhh",
    "inn": "id",
    "phone_am": "phone",
    "phone_ru": "value",
    "regions_am": "query",
    "regions_ru": "query",
    "chart_of_accounts_am": "code",
    "chart_of_accounts_ru": "code",
    "payroll_am": "gross",
    "invoice": "document",
}


def _build_input(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    """Translate a request body into the input dict the validator expects.

    Resolution order:
      1. ``{"value": "<str>"}`` → ``{"<primary_key>": "<str>"}`` (using
         :data:`_VALUE_KEY`, falling back to ``"value"`` as the key).
      2. ``{"value": {...}}`` → the dict as-is (multi-field validators).
      3. ``{"raw": {...}}`` → the dict as-is.
      4. Otherwise → the body itself is the input dict.
    """
    if "value" in body:
        v = body["value"]
        if isinstance(v, str):
            return {_VALUE_KEY.get(kind, "value"): v}
        if isinstance(v, dict):
            return v
    if "raw" in body and isinstance(body["raw"], dict):
        return body["raw"]
    return body


def _run_validator(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the named validator on a wrapped body.

    Always returns a dict with an ``ok`` key (added if the validator didn't
    emit one — this is the contract documented on the public routes).
    Exceptions become ``{"ok": false, "error": ..., "input": ...}``.
    """
    try:
        fn = get_validator(kind)
    except KeyError as exc:
        return {"ok": False, "error": str(exc), "input": body}
    try:
        input_data = _build_input(kind, body)
        result = fn(input_data)
    except Exception as exc:  # noqa: BLE001 — we want to surface everything
        logger.exception("Validator %s raised on input %r", kind, body)
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "input": body,
        }
    if not isinstance(result, dict):
        result = {"value": result}
    # Ensure 'ok' is present — most validators emit it, but a few (e.g.
    # vat_return, model_policy) return numeric/dict payloads without an
    # explicit ok flag. Default to True (the validator ran successfully).
    if "ok" not in result:
        result = {**result, "ok": True}
    return result


# ---------------------------------------------------------------------------
# Pydantic request body schemas. ``extra="allow"`` so multi-field validators
# (chat_client, model_catalog, settings_store, …) can accept their full
# payload at the top level.
# ---------------------------------------------------------------------------


class _BaseBody(BaseModel):
    """Common config: allow extras, ignore unknown fields."""

    model_config = ConfigDict(extra="allow")


class ValidateRequest(_BaseBody):
    """Body for ``POST /validate/<kind>``.

    The simple case is ``{"value": "<string>"}`` — the server wraps it
    into the validator's primary input key automatically. For multi-field
    validators, pass ``{"value": <dict>}`` or ``{"raw": <dict>}`` or the
    full input dict at the top level.
    """

    value: Optional[Any] = None
    raw: Optional[Any] = None


class BatchRequest(_BaseBody):
    """Body for ``POST /batch/<kind>`` — a list of values to validate."""

    values: list[Any]


# ---------------------------------------------------------------------------
# FastAPI app.
# ---------------------------------------------------------------------------

app = FastAPI(
    title="A1 Validator",
    version=a1_validator.__version__,
    description=(
        "REST API for the 23 SBOSS sovereign business ID validators vendored "
        "under `a1_validator._vendored`. Every public validator function is "
        "exposed as a pair of POST routes (`/validate/<kind>` and "
        "`/batch/<kind>`). The response is always HTTP 200; check the body's "
        "`ok` field for the per-call outcome."
    ),
    contact={"name": "A1 Suite", "email": "ops@a1-suite.local"},
    license_info={"name": "MIT"},
)


@app.get("/", response_model=None, tags=["meta"])
def root() -> dict[str, Any]:
    """Service discovery: name, version, and the 23 validator names."""
    return {
        "name": "a1-validator",
        "version": a1_validator.__version__,
        "validators": list_kinds(),
    }


@app.get("/validators", tags=["meta"])
def validators() -> dict[str, Any]:
    """Return the list of 23 public validator names."""
    return {"validators": list_kinds()}


# ---------------------------------------------------------------------------
# Per-validator route registration.
#
# We register one route pair per public validator name so the OpenAPI
# schema shows all 23 validators as separate operations (51 paths total
# including the 5 built-in FastAPI paths: /, /validators, /docs,
# /openapi.json, /redoc).
# ---------------------------------------------------------------------------


def _make_validate_handler(kind: str) -> Callable[[ValidateRequest], dict[str, Any]]:
    def handler(body: ValidateRequest) -> dict[str, Any]:
        # Drop None fields so the body sent to _build_input is the smallest
        # reasonable representation (e.g. {"value": "00123456"} for the
        # simple case rather than {"value": "00123456", "raw": null}).
        payload = body.model_dump(exclude_none=True)
        return _run_validator(kind, payload)

    handler.__name__ = f"validate_{kind}"
    handler.__doc__ = f"Run the `{kind}` validator on `{{value: <string>}}`."
    return handler


def _make_batch_handler(kind: str) -> Callable[[BatchRequest], dict[str, Any]]:
    def handler(body: BatchRequest) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for item in body.values:
            # Each batch item can be a string (wrapped via the primary
            # input key) or a dict (passed through as the full input).
            item_body = {"value": item} if not isinstance(item, dict) else item
            results.append(_run_validator(kind, item_body))
        return {"results": results}

    handler.__name__ = f"batch_{kind}"
    handler.__doc__ = f"Run the `{kind}` validator on a list of values."
    return handler


for _kind in list_kinds():
    app.post(
        f"/validate/{_kind}",
        name=f"validate_{_kind}",
        tags=["validate"],
        summary=f"Validate a single value with `{_kind}`",
        response_model=None,
    )(_make_validate_handler(_kind))

    app.post(
        f"/batch/{_kind}",
        name=f"batch_{_kind}",
        tags=["batch"],
        summary=f"Batch-validate a list of values with `{_kind}`",
        response_model=None,
    )(_make_batch_handler(_kind))


__all__ = ["app"]
