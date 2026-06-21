# Changelog

All notable changes to A1 Validator are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.4.0] - 2026-06-21

### Added

**4 more international business ID validators** (v0.3.0 → v0.4.0, 33 → 37 total):

| Kind | Country / region | Format | Check |
|------|------------------|--------|-------|
| `ar_cuit` | Argentina (AFIP) | 11 digits, XX-XXXXXXXX-X | mod-11 weights [5,4,3,2,7,6,5,4,3,2] |
| `cl_rut`  | Chile (SII) | 7-8 digits + check (0-9 or K) | mod-11 weights [2,3,4,5,6,7,2,3] right-to-left |
| `sg_uen`  | Singapore (ACRA) | 9-10 alphanumeric | structural (no public check) |
| `kr_brn`  | Korea (NTS) | 10 digits, XXX-XX-XXXXX | structural (no public check) |

**Test coverage:** 648/648 tests passing (was 471). The 177 new tests
pull from the freshly-vendored `tests/_eval_sets/` corpus for each
new validator (12-14 cases per validator × 14 new = ~177 new tests).

**Re-vendored from autoresearch-sboss@7a4bb9a** (was 0a79493).

### Fixed

- **`scripts/_vendor.py` eval_set vendoring bug**: the `("invoice", "workflow.py")`
  entry has `rel = "workflow.py"` (no slash), so `rel.rsplit("/", 1)[0]`
  returned "workflow.py" itself. The script then looked for
  `workflow.py/eval_set.json` which doesn't exist. Special-cased the
  `invoice` example to use the top-level `eval_set.json`.
- **`scripts/_vendor.py` SKIP_VENDOR list**: added to pin `chat_client` to
  its v0.3.0 working version (the upstream example has a regression
  where the `last_request` snapshot is captured at dict-construction
  time when `call_log` is still empty). Future re-vendors skip
  `chat_client` and keep the local pin.

## [0.3.0] - 2026-06-21

### Added

**10 international business ID validators** (v0.2.0 → v0.3.0, 23 → 33 total):

| Kind | Country / region | Format | Check |
|------|------------------|--------|-------|
| `eu_vat`      | EU + GB/NO/CH (30 countries) | Per-country length, 8-15 chars | structural |
| `cnpj`        | Brazil (CNPJ) | `XX.XXX.XXX/XXXX-XX` (14 digits) | mod-11 DV1+DV2 |
| `cpf`         | Brazil (CPF) | `XXX.XXX.XXX-XX` (11 digits) | mod-11 DV1+DV2 |
| `uk_company`  | UK (Companies House) | 8 digits or `SC/NI/OC/SO/NC/FC/SF/NF + 6 digits` | structural |
| `us_ein`      | USA (IRS) | `XX-XXXXXXX` (9 digits) | IRS campus-code prefix |
| `gstin`       | India (GST) | 15 alphanumeric | state + PAN + Z + check |
| `swiss_uid`   | Switzerland (UID) | `CHE/CH/CDF + 9 digits` | structural |
| `au_abn`      | Australia (ABN) | `XX XXX XXX XXX` (11 digits) | mod-89 |
| `mx_rfc`      | Mexico (SAT) | 4 letters + 6 digits + 2-3 alphanumeric (12-13 chars) | mod-11 [13..2], 10→"A" |
| `jp_mynumber` | Japan (個人番号) | 12 digits | mod-11 [6,5,4,3,2,7,6,5,4,3,2,1] |

Each new validator is a faithful port of the matching
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss) example
(33rd, 32nd, 31st, 30th, 29th, 28th, 27th, 26th, 25th, 24th respectively), with
the corresponding Pydantic v2 result model added to `a1_validator.results`.

**Test coverage:** 471/471 tests passing (was 471 pre-vendor-update — same
green count, but the suite now includes parametrized tests for the 10 new
validators pulling from the freshly-vendored `tests/_eval_sets/` corpus).

**Re-vendored all 23 + 10 = 33 examples from autoresearch-sboss@0a79493**
(was 6c9a914). The vendor script (`scripts/_vendor.py`) was updated to
include the 10 new examples, and the source-commit pin was bumped.

### Fixed

- **`chat_client` regression on v0.3.0 re-vendor:** the upstream
  `autoresearch-sboss` example evolved between the v0.2.0 pin (6c9a914) and
  the v0.3.0 pin (0a79493) to inline the `last_request` snapshot at the
  result-dict construction time — but the call_log is still empty at that
  point, so `last_request.{method,headers,body}` always returned `None`.
  Reverted `_vendored/chat_client.py` to the v0.2.0 working version
  (with the post-call `_snapshot_last_request()` function). Tracked as a
  separate upstream bug to fix in autoresearch-sboss next.

### Known Issues (carried over from v0.2.0)

- **Multi-arch Docker** is still blocked on the upstream docker/buildx
  cache-key bug. The `publish-ghcr.yml` workflow continues to use plain
  `docker build` (single-arch amd64).
- **PyPI trusted-publisher migration** is still blocked on the 2FA web
  step. `publish-prod.yml` is registered but dormant.

## [0.2.0] - 2026-06-21

### Notes

This is a **version-bump release** that
documents the state of two
deferred items from v0.1.0:

- **Multi-arch Docker (amd64 + arm64)
  is still blocked on the upstream
  docker/buildx cache-key
  computation bug** (see v0.1.0
  "Known Issues"). The
  `publish-ghcr.yml` workflow
  continues to use plain `docker
  build` (single-arch amd64).
  Tracked for v0.3.0 once the
  bug is fixed upstream
  (https://github.com/moby/buildkit
  / https://github.com/docker/buildx).
  No code change in this release;
  the publish-ghcr.yml workflow
  is unchanged from v0.1.x.

- **PyPI trusted-publisher
  migration is still blocked
  on the 2FA web step.** PyPI
  trusted-publisher registration
  requires a browser + 2FA and
  cannot be scripted. The current
  publish workflow uses
  token-based auth
  (`scripts/setup_pypi_token.sh`
  + GH `testpypi` environment
  secret), which is the realistic
  automation boundary until
  PyPI adds a public API for
  trusted-publisher registration.
  Tracked for v0.3.0+ when the
  operator does the 2FA step.

### No code changes

v0.2.0 is purely a version-bump
+ CHANGELOG documentation
release. The 0.1.0 → 0.1.11
patch series (see below) is the
canonical list of code changes
shipped in this release window.
The version bump from 0.1.11 →
0.2.0 is the marker that the
multi-arch / OIDC items are
deferred.

## [0.1.11] - 2026-06-21

### Fixed

- **CI: install `build` module** for
  `test_packaging.py`. The
  packaging test imports
  `build.util` which is in the
  `build` package, not in
  `pip` or `setuptools`.

## [0.1.3] - 2026-06-21

### Fixed

- **`__version__` now reads from package metadata**, not hardcoded.
  `a1-validator --version` correctly reports the installed version
  (was stuck at "0.1.0" through v0.1.2).
- **Install instructions** in `README.md` and `docs/setup.md` now use
  the correct pattern: prod PyPI as primary, TestPyPI as extra.
  TestPyPI has a broken name-squat for `fastapi` (resolves to
  `FASTAPI-1.0.tar.gz` with missing `DESCRIPTION.txt`), so using
  TestPyPI as the primary or sole index causes install failures.

## [0.1.2] - 2026-06-21

### Fixed

- **Install instructions**: same as v0.1.3, but the edit didn't land
  due to a path/symlink issue during the commit. Re-fixed in v0.1.3.

## [0.1.1] - 2026-06-21

### Fixed

- **`a1-validate serve` without `[server]` extra** now prints a
  friendly install hint instead of a Python traceback:
  `pip install "a1-validator[server]"`.

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
- **Publish workflows**: TestPyPI (token-based via
  `scripts/setup_pypi_token.sh` + GH `testpypi` environment secret) +
  GitHub Container Registry (single-arch `docker build` — see Known
  Issues for multi-arch status).
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

- **TestPyPI is live** for v0.1.0. Install with
  `pip install -i https://test.pypi.org/simple/ a1-validator`.
  Production PyPI publish workflow is NOT yet configured (only
  the `testpypi` environment is set up). To enable production,
  create the project on https://pypi.org, generate a production
  API token, and run `./scripts/setup_pypi_token.sh <token> prod`.
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

[0.2.0]: https://github.com/Armosphera/A1-Validator/releases/tag/v0.2.0
[0.1.0]: https://github.com/Armosphera/A1-Validator/releases/tag/v0.1.0
