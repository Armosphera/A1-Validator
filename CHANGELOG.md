# Changelog

All notable changes to A1 Validator are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

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
