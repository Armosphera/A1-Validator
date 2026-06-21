# Changelog

All notable changes to A1 Validator are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.1.0] - 2026-06-21

### Added

- **23 SBOSS business ID validators** bundled as a single Python
  package `a1_validator`:
  - **Armenia (AM)**: HHVH (Armenian taxpayer ID), phone normalization,
    e-invoice validator, payroll rules, regions lookup (11 marzes),
    chart of accounts (623 accounts, 9 classes), VAT return
    computation, VAT return form validator, top-level invoice extractor.
  - **Russia (RU)**: ru-identifiers (ИНН / КПП / ОГРН / ОГРНИП / СНИЛС
    dispatcher), phone normalization, ru-einvoice (счёт-фактура / УПД)
    validator, payroll (5-band НДФЛ + страховые взносы), regions
    lookup (83 federal subjects, ISO 3166-2:RU), chart of accounts
    (73 accounts per Приказ Минфина № 94н), VAT engine (2026 reform,
    УСН 5/7%).
  - **AI / config**: model-policy resolver (with `source` tracking),
    settings store (file-backed, 0600 perms), model catalog (live
    OpenRouter with mock-injection seam), open-notebook RAG connector,
    chat client (OpenAI-compatible), supplemental sources policy,
    product-research primitives.
- **CLI** `a1-validate` with 5 subcommands: `<kind> <value>` (single
  validate, JSON output), `list` (23 validators + one-liners),
  `batch <kind> <file>` (JSON eval-set OR plain-text auto-detected),
  `serve` (HTTP service), `--version`.
- **HTTP service** (FastAPI) on `a1-validate serve`: 48 OpenAPI paths
  (23 validators × 2 endpoints + meta), Swagger UI at `/docs`,
  ReDoc at `/redoc`. `POST /validate/{kind}` and `POST /batch/{kind}`.
- **Docker image** at `ghcr.io/armosphera/a1-validator:v0.1.0`
  (linux/amd64, 28MB, python:3.12-slim + tini, non-root).
- **Docs site** (mkdocs-material) with 6 pages: home, validators
  (auto-generated), CLI, HTTP service, deploy, about.
- **CI** (GitHub Actions): Python 3.10/3.11/3.12 matrix, ruff lint,
  pytest with coverage gate (≥80%).
- **Publish workflows**: TestPyPI (OIDC trusted publishing) +
  GitHub Container Registry (multi-arch-ready, single-arch shipped
  for v0.1.0 due to docker/buildx cache-key bug — see Known
  Issues).
- **Security policy** (`.github/SECURITY.md`).
- **Dependabot** for pip updates.

### Source of truth

Every validator is ported from the
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss)
framework, which in turn ported each module from
[A1-Localization-AM](https://github.com/Armosphera/A1-Localization-AM),
[A1-Localization-RU](https://github.com/Armosphera/A1-Localization-RU),
and [A1-AI-Core](https://github.com/samstep74/A1-AI-Core). Each
validator ships with its own `eval_set.json` test cases that match
the original JavaScript source at 100% baseline.

### Test contract

- 469 pytest cases pass, 86% line coverage.
- All 23 validator eval sets are vendored under
  `tests/_eval_sets/<name>.json` and re-played in
  `tests/test_validators.py`.

### Known issues

- **TestPyPI trusted publisher not configured.** The workflow
  `.github/workflows/publish-testpypi.yml` is correctly configured
  with OIDC (`id-token: write`) and references the `testpypi`
  GitHub environment, but the PyPI-side trusted publisher has not
  been added. To enable `pip install a1-validator` from TestPyPI,
  add the publisher at
  https://test.pypi.org/manage/account/publishing/ with
  owner=`Armosphera`, repo=`A1-Validator`, workflow
  filename=`publish-testpypi.yml`, environment=`testpypi`.
- **Single-arch Docker image (amd64 only) for v0.1.0.** The
  planned multi-arch (amd64 + arm64) hit a docker/buildx cache-key
  bug where `COPY` operations intermittently fail with
  `"/README.md: not found"` on the buildkit cache-key computation.
  Tracked for v0.2.0 with a workaround: switched to plain
  `docker build` (no buildx) and a simplified `.dockerignore`
  (removed the `*.md / !README.md` exception pattern that
  triggered the bug). When docker/buildx fixes the bug
  upstream, multi-arch can be re-enabled.
- **License is Armosphera Proprietary** (not MIT as in the
  upstream source repos). This is an Armosphera LLC internal
  product, not an open-source release.

[0.1.0]: https://github.com/Armosphera/A1-Validator/releases/tag/v0.1.0
