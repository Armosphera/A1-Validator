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

## CLI usage

Installing the package also installs an `a1-validate` console script:

```bash
# Validate a single value — result is printed as JSON to stdout.
# Exit 0 if ok=true, exit 1 if ok=false (or the kind is unknown).
a1-validate hhvh 00123456
# → {"ok": true, "normalized": "00123456", "error": null}
a1-validate hhvh 99999999   # all-same-digit HHVH is invalid
# → {"ok": false, "normalized": "99999999", "error": "ՀՎՀՀ-ն անվավեր է"}

# List all 23 validators with a one-line description each.
a1-validate list
# → a1-validator 0.1.0 — 23 SBOSS validators:
#     hhvh       Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ)
#     inn        Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher ...
#     ...

# Batch-run a vendored eval-set file (array of {input, expected} cases).
# Exit 0 if every case matches, exit 1 if any case fails.
a1-validate batch hhvh tests/_eval_sets/hhvh.json
# → {"kind": "hhvh", "mode": "eval_set", "total": 20, "ok": 20, "fail": 0, ...}

# Batch-run a plain-text file (one raw value per line). Each value is wrapped
# under the validator's canonical single-string input key. Exit 0 only if
# every line is ok=true.
cat values.txt | xargs -I{} echo {} | a1-validate batch hhvh values.txt
# → {"kind": "hhvh", "mode": "lines", "total": 3, "ok": 2, "fail": 1, ...}

# Boot the FastAPI HTTP service (requires the [server] extra).
a1-validate serve --host 127.0.0.1 --port 8000 --reload
# → uvicorn running on http://127.0.0.1:8000

# Print the package version and exit.
a1-validate --version
# → a1-validator 0.1.0
```

For multi-input validators (e.g. `vat_return`, `chat_client`), pass the input
as a JSON object on the command line:

```bash
a1-validate vat_return '{"net": 100000, "outputVat": 20000, "inputVat": 5000}'
# → {"net": 100000, "outputVat": 20000, "inputVat": 5000, "payable": 15000, ...}
```

Single-string validators (the 11 kinds whose vendored `validate()` reads
exactly one field) accept a plain value and auto-wrap it under the
canonical input key — so `a1-validate hhvh 00123456` is sugar for
`a1-validate hhvh '{"hvhh": "00123456"}'`.

Pipe the JSON output straight into `jq`:

```bash
a1-validate hhvh 00123456 | jq -r .normalized
# → 00123456
```

The `batch` subcommand auto-detects the input file's format:

* **JSON eval-set** (`tests/_eval_sets/<name>.json`) — array of
  `{input, expected}` cases. Each `input` is validated against `expected`
  under the same subset-equality contract as the pytest suite.
* **Plain text** — one raw value per line. Each non-blank line is wrapped
  under the validator's canonical single-string input key and validated;
  pass/fail is read from the validator's `ok` field. Only works for the
  11 single-input validators — multi-input validators reject this mode
  with a clear error.

The output `mode` field (`"eval_set"` or `"lines"`) tells you which path
was taken for the summary.

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

## License

MIT — same as the upstream
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss) corpus.
Vendor source: commit `6c9a9149f1dc8b7a5430d542de19f564a078418c`.