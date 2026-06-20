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

## License

MIT — same as the upstream
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss) corpus.
Vendor source: commit `6c9a9149f1dc8b7a5430d542de19f564a078418c`.