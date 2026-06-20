# CLI

The package installs an `a1-validate` console script. It exposes four
subcommands plus a default-form validation:

| Subcommand | What it does |
| ---------- | ------------ |
| `a1-validate <kind> <value>` | Validate a single value, print JSON to stdout. |
| `a1-validate list` | List all 23 validators with one-line descriptions. |
| `a1-validate batch <kind> <file>` | Run every case in a vendored eval-set (JSON) or a plain-text list (one value per line). |
| `a1-validate serve` | Boot the FastAPI HTTP service from `a1_validator.server`. Requires `[server]` extra. |
| `a1-validate --version` / `a1-validate version` | Print `a1_validator.__version__` and exit. |

Exit codes:

* `0` — validation succeeded (`ok=true`) or the informational command completed cleanly.
* `1` — validation failed (`ok=false`), the kind is unknown, or the
  input was malformed.
* `2` — internal error (the vendored validator raised an unexpected
  exception, the eval-set file is unreadable, etc.).

## Default form: validate one value

```bash
# Single-string validators — wrap under the canonical input key.
a1-validate hhvh 00123456
# → {"ok": true, "normalized": "00123456", "error": null}

# Same validator, invalid input — still well-formed JSON, but ok=false.
a1-validate hhvh 99999999
# → {"ok": false, "normalized": "99999999", "error": "ՀՎՀՀ-ն անվավեր է"}

# Multi-field validator — pass the full input dict as JSON.
a1-validate vat_return '{"net": 100000, "outputVat": 20000, "inputVat": 5000}'
# → {"net": 100000, "outputVat": 20000, "inputVat": 5000, "payable": 15000, ...}

# Pipe the JSON output into jq.
a1-validate hhvh 00123456 | jq -r .normalized
# → 00123456
```

The 11 single-string validators accept a bare value (auto-wrapped under
their canonical key — `hhvh` → `hvhh`, `inn` → `id`, `phone_am` → `phone`,
…). The remaining 12 multi-field validators require a JSON object and
raise a clear error if you pass a bare string.

## List all 23 validators

```bash
a1-validate list
# a1-validator 0.1.0 — 23 SBOSS validators:
#     hhvh                 Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ)
#     inn                  Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher ...
#     model_policy         AI model-policy resolver (module → model)
#     vat_return           Armenian VAT return compute (sales/purchases → owed)
#     ...
```

## Batch-run an eval set

```bash
# Vendored eval-set JSON (matches tests/_eval_sets/<name>.json).
a1-validate batch hhvh tests/_eval_sets/hhvh.json
# → {"kind": "hhvh", "mode": "eval_set", "total": 20, "ok": 20, "fail": 0, "failures": []}

# Plain-text file — one raw value per line (single-string validators only).
printf '00123456\n12345678\n99999999\n' > ids.txt
a1-validate batch hhvh ids.txt
# → {"kind": "hhvh", "mode": "lines", "total": 3, "ok": 2, "fail": 1, "failures": [...]}
```

The `mode` field in the output (`"eval_set"` or `"lines"`) tells you
which path was taken. Eval-set mode compares against the file's
`expected` field; plain-text mode only checks `ok=true`.

## Serve the HTTP API

```bash
pip install "a1-validator[server]"   # one-time
a1-validate serve --host 0.0.0.0 --port 8000
# → uvicorn running on http://0.0.0.0:8000
```

See the [HTTP service docs](http.md) for the full endpoint list and curl
examples. Equivalent direct invocation:

```bash
uvicorn a1_validator.server:app --host 0.0.0.0 --port 8000 --workers 4
```

## Version

```bash
a1-validate --version
# → a1-validator 0.1.0
```
