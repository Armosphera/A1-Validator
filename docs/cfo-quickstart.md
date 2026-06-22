# A1 Validator — 60-second Quickstart for CFOs

> If you're a finance / ops / engineering lead at a company that
> touches cross-border suppliers, customers, or tax authorities,
> this is the only page you need to read.

## What it does

`a1-validator` is a single Python library that **validates 37 business
ID formats** from 15+ countries — Armenian (HHVH), Russian (INN / OGRN
/ SNILS), Brazilian (CNPJ / CPF), EU VAT, US EIN, UK Company, Indian
GSTIN, Australian ABN, Swiss UID, Mexican RFC, Japan My Number,
Argentine CUIT, Chilean RUT, Singapore UEN, Korean BRN, and more.
100% offline. No network calls. No LLM. 709/709 tests passing.

| | |
|---|---|
| **Use case** | Validate a customer / vendor / invoice's tax ID at the API boundary before saving it to your finance system. |
| **Why it matters** | A typo in a tax ID is a blocked payment. Validating at intake = clean books at close. |
| **What you get** | `{ ok: bool, normalized: str, error: str|null }` — every validator returns the same shape. |
| **Latency** | < 1ms per call. |
| **Compliance** | Armosphera Proprietary. Source-visible. No telemetry. No model calls. |

## 60-second install

```bash
# TestPyPI (current — switch to prod PyPI after your 2FA setup)
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ a1-validator

# Or run as a Docker sidecar (production-grade)
docker pull ghcr.io/armosphera/a1-validator:v0.4.0
docker run -d --name a1-validator -p 8000:8000 \
  ghcr.io/armosphera/a1-validator:v0.4.0
```

## 30-second use

```python
import a1_validator

# Validate an Armenian taxpayer ID (8 digits)
a1_validator.hhvh({"hvhh": "00123456"})
# → {"ok": True, "normalized": "00123456", "error": null}

# Validate a Russian INN (10 or 12 digits)
a1_validator.inn({"id": "7707083893"})
# → {"ok": True, "normalized": "7707083893", "kind": "inn", "error": null}

# Validate a Brazilian CNPJ (with or without separators)
a1_validator.cnpj({"cnpj": "11.222.333/0001-81"})
# → {"ok": True, "normalized": "11222333000181", "error": null}

# Validate a Mexico RFC, Japan My Number, EU VAT, US EIN, India GSTIN, ...
# All 41 follow the same pattern. See `a1_validator.list_kinds()` for the full list.
```

The full validator list and live example outputs for every one of
them are at
[armosphera.github.io/A1-Validator/validators/](https://armosphera.github.io/A1-Validator/validators/).

## 10-second use as an HTTP service

```bash
# Server is already running on :8000 from the docker run above.
# Now wire it into your finance app:
curl -X POST http://a1-validator:8000/validate/hvvh \
  -H 'content-type: application/json' \
  -d '{"value": {"hvhh": "00123456"}}'
# → 200 OK
# → {"ok": true, "normalized": "00123456", "error": null}

curl -X POST http://a1-validator:8000/validate/cnpj \
  -H 'content-type: application/json' \
  -d '{"value": {"cnpj": "11.222.333/0001-81"}}'
# → 200 OK
# → {"ok": true, "normalized": "11222333000181", "error": null}
```

Every endpoint shape, the OpenAPI spec, and the health check
(`GET /`) are at
[armosphera.github.io/A1-Validator/http/](https://armosphera.github.io/A1-Validator/http/).

## Why it ships in two places

1. **Python library** (`pip install a1-validator`) — for hot-path
   validation in your Python finance / data / ETL stack. 0.1ms latency,
   no network.
2. **HTTP service** (Docker image) — for any language: Node, Ruby, Go,
   .NET, etc. call it over the wire. ~1ms in-cluster.

You don't need both. Start with one.

## What's not in the box

`a1-validator` is a **validation** library, not a verification
service. It catches typos, format errors, and check-digit mismatches
**at intake**. It does NOT:

- Call the actual tax authority to confirm the ID is registered
  (that's a 3rd-party verification service — different product)
- Generate / issue new IDs
- Replace your KYC / onboarding workflow

Think of it as a strict regex+check-digit library that's been
factored out of the SBOSS sovereign business-ops stack. Drop it
in front of your `INSERT INTO customers` and you stop bad data
from ever hitting the books.

## When to call it

- **Customer onboarding** — validate the HHVH/INN/CNPJ/EIN before
  creating the customer record.
- **Vendor onboarding** — same.
- **Invoice intake** — validate the supplier's tax ID on the invoice
  before posting to GL.
- **Bank reconciliation** — validate the counterparty tax ID on
  every bank line before matching it to a vendor.
- **Period close** — re-validate the entire customer/vendor table to
  catch drift (someone typed "0000" instead of "0001" in the
  spreadsheet import).

## Pricing & license

`a1-validator` is **Armosphera Proprietary**. Free to use within
SBOSS sovereign business-ops stacks. Contact
[ops@armosphera.dev](mailto:ops@armosphera.dev) for redistribution
or SaaS-embedding terms.

The companion framework
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss)
is MIT-licensed — that one is the eval-loop harness for tuning
workflows like these.

## Where to go next

- **Full validator reference**: [validators.md](validators.md) — 37
  examples, one per validator, with real input + real output
- **HTTP service spec**: [http.md](http.md) — OpenAPI, error codes,
  retry semantics
- **CLI usage**: [cli.md](cli.md) — `a1-validate` for shell pipelines
- **Deploy recipes**: [deploy.md](deploy.md) — Docker, Kubernetes,
  systemd unit, pm2 config
- **CHANGELOG**: [CHANGELOG.md](CHANGELOG.md) — what's in v0.4.0
- **Source**: [github.com/Armosphera/A1-Validator](https://github.com/Armosphera/A1-Validator)

## Used by

- **[SBOS-A1-ERP](https://github.com/Armosphera/SBOS-A1-ERP)** — Armenian
  SME ERP foundation. v1.0.0+ uses A1-Validator as the source of
  truth for HVVH (Armenian TIN) validation on customer / vendor /
  invoice / vendor-bill / CRM contact / CRM lead / POS sale writes,
  plus an on-demand `/validate-hvhh` endpoint for drift detection
  (run after a year of edits, see if the customer's TIN is still
  valid). The Node 20+ HTTP client is at
  `lib/a1-validator-client.js` and the on-demand wrapper is at
  `server/finance/validate-hvhh.js`.

## v0.5.0 changes (since v0.4.0)

- 4 more international business IDs (37 → 41): added Argentine CUIT
  (already present but now in CSV), Chilean RUT, Singapore UEN,
  Korean BRN.
- New `a1-validate validate-csv` CLI for batch validation (the
  import-time check that a CSV of new suppliers is clean before
  you write it to the DB).
- New live-server integration tests that catch the `_VALUE_KEY`
  class of bugs (a real HTTP server can return JSON with keys that
  the in-process TestClient can't simulate).
