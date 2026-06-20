# HTTP service

Installing `a1-validator[server]` pulls in FastAPI + uvicorn and gives you
a small REST app at `a1_validator.server:app`. Boot it with the bundled
CLI:

```bash
pip install "a1-validator[server]"
a1-validate serve --host 0.0.0.0 --port 8000
# → uvicorn running on http://0.0.0.0:8000
```

…or directly with uvicorn (e.g. behind gunicorn):

```bash
uvicorn a1_validator.server:app --host 0.0.0.0 --port 8000 --workers 4
```

Then open <http://localhost:8000/docs> for the auto-generated Swagger UI,
or <http://localhost:8000/openapi.json> for the raw OpenAPI 3.1 schema
(51 paths).

## Endpoints

| Method | Path                  | Body                              | Notes                                         |
| ------ | --------------------- | --------------------------------- | --------------------------------------------- |
| `GET`  | `/`                   | —                                 | `{name, version, validators: [23 names]}`     |
| `GET`  | `/validators`         | —                                 | `{validators: [23 names]}`                    |
| `POST` | `/validate/<kind>`    | `{"value": "<string>"}`           | One route per validator — see list below      |
| `POST` | `/batch/<kind>`       | `{"values": ["…", "…", …]}`       | Same per-kind shape; returns `{results: …}`   |
| `GET`  | `/docs`               | —                                 | Swagger UI                                    |
| `GET`  | `/openapi.json`       | —                                 | OpenAPI 3.1 schema (51 paths)                 |

`<kind>` is one of: `hhvh`, `inn`, `model_policy`, `vat_return`, `payroll_am`,
`chart_of_accounts_am`, `vat_return_form`, `phone_am`, `regions_am`,
`einvoice_am`, `chat_client`, `phone_ru`, `ru_einvoice`, `payroll_ru`,
`regions_ru`, `chart_of_accounts_ru`, `vat_ru`, `settings_store`,
`model_catalog`, `supplemental_sources`, `open_notebook`, `product_research`,
`invoice`.

The response is **always HTTP 200** for known kinds — check the body's `ok`
field for the per-call outcome. Validator exceptions become
`{"ok": false, "error": "<ExceptionClass>: <message>", "input": …}`.

## Input shape

The body is intentionally flexible so the simple single-string validators
(`hhvh`, `inn`, `phone_am`, …) and the multi-field ones (`chat_client`,
`vat_ru`, `settings_store`, …) share the same endpoint:

```jsonc
// Simple case — the server wraps the string under the kind's primary key.
{ "value": "00123456" }                 // → { "hvhh": "00123456" } for hhvh
{ "value": "7707083893" }               // → { "id":   "7707083893" } for inn

// Multi-field case — pass the validator's full input dict as `value`.
{ "value": { "openrouter": {…}, "maxOutputTokens": 256, "operation": "chat", "kwargs": {} } }

// Or as `raw` — alias for the same passthrough.
{ "raw": { "openrouter": {…}, "maxOutputTokens": 256 } }

// Or at the top level — for kind-specific input dicts the server treats
// the body itself as the input.
{ "hvhh": "00123456" }
```

## Curl examples

```bash
# Discovery — list the 23 validator names.
curl -s http://localhost:8000/
# → {"name": "a1-validator", "version": "0.1.0", "validators": ["hhvh", "inn", ...]}

# Validate a single HHVH (Armenian taxpayer ID). 8-digit canonical form.
curl -s -X POST http://localhost:8000/validate/hhvh \
  -H 'Content-Type: application/json' \
  -d '{"value": "00123456"}'
# → {"ok": true, "normalized": "00123456", "error": null}

# Same endpoint, bad input — still 200, but ok=false in the body.
curl -s -X POST http://localhost:8000/validate/hhvh \
  -H 'Content-Type: application/json' \
  -d '{"value": "99999999"}'
# → {"ok": false, "normalized": "99999999", "error": "ՀՎՀՀ-ն անվավեր է"}

# Russian INN (legal entity) — server wraps the string under {"id": …}.
curl -s -X POST http://localhost:8000/validate/inn \
  -H 'Content-Type: application/json' \
  -d '{"value": "7707083893"}'
# → {"ok": true, "normalized": "7707083893", "kind": "inn_legal", "error": null}

# Batch — 3 HHVHs in one call.
curl -s -X POST http://localhost:8000/batch/hhvh \
  -H 'Content-Type: application/json' \
  -d '{"values": ["00123456", "12345678", "99999999"]}'
# → {"results": [
#      {"ok": true,  "normalized": "00123456", "error": null},
#      {"ok": true,  "normalized": "12345678", "error": null},
#      {"ok": false, "normalized": "99999999", "error": "ՀՎՀՀ-ն անվավեր է"}
#    ]}

# Multi-field validator — pass the full input dict as `value`.
curl -s -X POST http://localhost:8000/validate/payroll_am \
  -H 'Content-Type: application/json' \
  -d '{"value": {"gross": 300000}}'
# → {"ok": true, "gross": 300000.0, "incomeTax": 36000.0, ...}
```

## Programmatic startup

The app object is a standard `fastapi.FastAPI` instance — mount it as a
sub-app, add middleware, or swap the OpenAPI metadata as needed. The
`app` reference is also reachable via `a1_validator.server:app`, so any
ASGI runner (uvicorn, hypercorn, granian, …) can host it.

```python
# examples/middleware.py
from a1_validator.server import app
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sboss.example.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

## See also

- :material-console: [CLI docs](cli.md) — the `a1-validate serve`
  subcommand is the same code path as `uvicorn a1_validator.server:app`.
- :material-rocket-launch: [Validators reference](validators.md) — the
  full per-kind input / output contract.
