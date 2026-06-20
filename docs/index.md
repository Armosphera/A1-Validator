# A1 Validator

**23 SBOSS sovereign business ID validators, packaged as a single importable
Python library.**

A faithful Python port of the 23 workflow validators published in
[Armosphera/autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss).
Each validator passes its full vendored `eval_set.json` corpus at the
upstream's baseline 100% match rate. Aimed at SBOSS sovereign-business-ops
stacks that need deterministic validation of Armenian and Russian
identifiers, chart-of-accounts codes, e-invoice shapes, and invoice field
extraction — without a network round-trip.

## Who it's for

- **SBOSS sovereign business-ops** integrations that need to validate
  Armenian (`HHVH`, phone, chart-of-accounts, e-invoice) and Russian
  (`INN` / `OGRN` / `SNILS`, payroll NDFL, regions, e-invoice) identifiers
  and forms in a hot path where a network call is unacceptable.
- **Finance-close tooling** that needs to recompute VAT returns,
  payroll withholdings, and chart-of-account mappings offline against a
  reproducible corpus.
- **AI agent frameworks** that need an offline safety net for
  LLM-backed extractors (`chat_client`, `model_catalog`,
  `product_research`, `invoice`) — every network-touching validator is
  transport-injectable for deterministic tests.

## Install

```bash
pip install a1-validator
```

For the optional FastAPI HTTP service + `a1-validate serve` CLI:

```bash
pip install "a1-validator[server]"
```

## Quick start

```python
import a1_validator

# Armenian taxpayer ID (HHVH)
a1_validator.hhvh({"hvhh": "00123456"})
# → {"ok": True, "normalized": "00123456", "error": None}

# Russian INN / OGRN / SNILS dispatcher
a1_validator.inn({"id": "7707083893"})
# → {"ok": True, "normalized": "7707083893", "kind": "inn_legal", "error": None}

# Unified dispatcher — same path the CLI and HTTP service use
a1_validator.validate("hhvh", {"hvhh": "00123456"})
a1_validator.validate("inn",  {"id":   "7707083893"})
```

Every validator returns a plain `dict`. The matching Pydantic v2 result
model is also exposed — `a1_validator.HHVHResult`, `a1_validator.INNResult`,
etc. — so typed consumers can do
`a1_validator.model_for("hhvh").model_validate(result)`.

## The 23 validators

| # | Kind | What it validates |
| -:| ---- | ----------------- |
|  1 | `hhvh`                 | Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ) |
|  2 | `inn`                  | Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (`ru-identifiers`) |
|  3 | `model_policy`         | AI model-policy resolver (module → model) |
|  4 | `vat_return`           | Armenian VAT return compute (sales/purchases → owed) |
|  5 | `payroll_am`           | Armenian payroll compute (gross → taxes/net) |
|  6 | `chart_of_accounts_am` | Armenian chart-of-accounts lookup + validate (623 accounts) |
|  7 | `vat_return_form`      | Armenian VAT-return form validation (line codes + amounts) |
|  8 | `phone_am`             | Armenian phone NSN/E.164/format |
|  9 | `regions_am`           | Armenian regions lookup (name/en/code → center) |
| 10 | `einvoice_am`          | Armenian e-invoice structural validation |
| 11 | `chat_client`          | OpenRouter chat client (mock-able HTTP transport) |
| 12 | `phone_ru`             | Russian phone NSN/E.164/format |
| 13 | `ru_einvoice`          | Russian e-invoice validate + XML build |
| 14 | `payroll_ru`           | Russian payroll (NDFL, insurance, monthly ops) |
| 15 | `regions_ru`           | Russian regions lookup (83 entries) |
| 16 | `chart_of_accounts_ru` | Russian chart-of-accounts lookup (73 accounts, 9 sections) |
| 17 | `vat_ru`               | Russian VAT rate helpers + valid-rate check |
| 18 | `settings_store`       | Local JSON settings store (read/write/list/delete) |
| 19 | `model_catalog`        | OpenRouter model catalog fetch + normalize |
| 20 | `supplemental_sources` | Supplemental research sources normalizer |
| 21 | `open_notebook`        | Notebook search/enable/normalize ops |
| 22 | `product_research`     | Product-research config + program render + decide |
| 23 | `invoice`              | Invoice field extractor (regex/mock, deterministic) |

See the [full reference](validators.md) for example inputs and outputs
per validator.

## What's next

- :material-rocket-launch: **[Validators →](validators.md)** — per-kind
  example inputs and outputs, generated from the live package.
- :material-console: **[CLI →](cli.md)** — `a1-validate` console script
  for one-shot validation, batch runs, and the FastAPI server.
- :material-cloud: **[HTTP service →](http.md)** — REST endpoints
  (auto-generated OpenAPI 3.1 schema, Swagger UI at `/docs`).
- :material-package-variant: **[Deploy →](deploy.md)** — install
  recipes, container images, and PyPI publishing notes.
- :material-information: **[About →](about.md)** — architecture, license,
  and the upstream `autoresearch-sboss` corpus this port tracks.

## License

MIT — same as the upstream
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss)
corpus. Vendor source: commit `6c9a9149f1dc8b7a5430d542de19f564a078418c`.
