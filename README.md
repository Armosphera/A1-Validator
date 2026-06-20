# A1 Validator

**23 SBOSS sovereign business ID validators, packaged as a single importable Python library.**

A faithful Python port of the 23 workflow validators published in
[Armosphera/autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss) —
each at its baseline 100% match rate against the upstream `eval_set.json` corpus.
Aimed at SBOSS sovereign-business-ops stacks that need deterministic validation of
Armenian and Russian identifiers, chart-of-accounts codes, e-invoice shapes, and
invoice field extraction — without a network round-trip.

## Install

```bash
pip install a1-validator
```

## Quick start

```python
import a1_validator

# Armenian taxpayer ID (HHVH)
a1_validator.hhvh({"hvhh": "00123456"})
# → {"ok": True, "normalized": "00123456", "error": None}

# Russian INN / OGRN / SNILS dispatcher
a1_validator.inn({"id": "7707083893"})
# → {"ok": True, "normalized": "7707083893", "kind": "inn", "error": None}

# Unified dispatcher
a1_validator.validate("hhvh", {"hvhh": "00123456"})
a1_validator.validate("inn",  {"id": "7707083893"})
```

Every validator returns a plain dict (and a matching Pydantic v2 result model is
exposed — `a1_validator.HHVHResult`, `a1_validator.INNResult`, …).

## The 23 validators

| Name | What it validates |
| ---- | ----------------- |
| `hhvh`                 | Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ) |
| `inn`                  | Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (`ru-identifiers`) |
| `model_policy`         | AI model-policy resolver (module → model) |
| `vat_return`           | Armenian VAT return compute (sales/purchases → owed) |
| `payroll_am`           | Armenian payroll compute (gross → taxes/net) |
| `chart_of_accounts_am` | Armenian chart-of-accounts lookup + validate (623 accounts) |
| `vat_return_form`      | Armenian VAT-return form validation (line codes + amounts) |
| `phone_am`             | Armenian phone NSN/E.164/format |
| `regions_am`           | Armenian regions lookup (name/en/code → center) |
| `einvoice_am`          | Armenian e-invoice structural validation |
| `chat_client`          | OpenRouter chat client (mock-able HTTP transport) |
| `phone_ru`             | Russian phone NSN/E.164/format |
| `ru_einvoice`          | Russian e-invoice validate + XML build |
| `payroll_ru`           | Russian payroll (NDFL, insurance, monthly ops) |
| `regions_ru`           | Russian regions lookup (83 entries) |
| `chart_of_accounts_ru` | Russian chart-of-accounts lookup (73 accounts, 9 sections) |
| `vat_ru`               | Russian VAT rate helpers + valid-rate check |
| `settings_store`       | Local JSON settings store (read/write/list/delete) |
| `model_catalog`        | OpenRouter model catalog fetch + normalize |
| `supplemental_sources` | Supplemental research sources normalizer |
| `open_notebook`        | Notebook search/enable/normalize ops |
| `product_research`     | Product-research config + program render + decide |
| `invoice`              | Invoice field extractor (regex/mock, deterministic) |

## Architecture

The port keeps each workflow's Python source under
`src/a1_validator/_vendored/<name>.py` so the package is self-contained and
diffable against upstream. The `run_workflow` eval-harness adapter is replaced
by a uniform `validate(input_data)` entry point in each vendored module, then
re-exported as `a1_validator.<name>` in `__init__.py`. The unified
`a1_validator.validate(kind, value)` dispatcher routes by validator name.

Pydantic v2 result models (one per validator) live in `a1_validator.results`.

## HTTP service

Every public validator is also exposed as a REST endpoint by a small FastAPI
app in `a1_validator.server`. Install the optional server extra and start
the service with the bundled `a1-validate serve` CLI:

```bash
pip install "a1-validator[server]"
a1-validate serve --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000/docs> for the auto-generated Swagger UI, or
<http://localhost:8000/openapi.json> for the raw OpenAPI 3.1 schema.

### Endpoints

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

### Input shape

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

### Curl examples

```bash
# Discovery — list the 23 validator names.
curl -s http://localhost:8000/

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

### Programmatic startup

If you prefer `uvicorn` directly (e.g. inside a container with gunicorn
managing workers), the import string is the same as the CLI uses:

```bash
uvicorn a1_validator.server:app --host 0.0.0.0 --port 8000 --workers 4
```

The app object is a standard `fastapi.FastAPI` instance — mount it as a
sub-app, add middleware, or swap the OpenAPI metadata as needed.

## License

MIT — same as the upstream
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss) corpus.
Vendor source: commit `6c9a9149f1dc8b7a5430d542de19f564a078418c`.