# Release notes — A1 Validator v0.1.0

**Tag:** [`v0.1.0`](https://github.com/Armosphera/A1-Validator/releases/tag/v0.1.0) (2026-06-21)

## What you can do today

```bash
# Pull the Docker image
docker pull ghcr.io/armosphera/a1-validator:v0.1.0
docker run --rm -p 8000:8000 ghcr.io/armosphera/a1-validator:v0.1.0

# Or install from source
git clone https://github.com/Armosphera/A1-Validator.git
cd A1-Validator
python -m pip install -e ".[server,dev]"

# CLI
a1-validate list
a1-validate hhvh 00123456                  # → ok=true, normalized="00123456"
a1-validate inn 7707083893                  # → ok=true, kind="legal"
a1-validate batch hhvh values.txt           # batch from file
a1-validate serve --port 8000              # HTTP service
```

## What ships in v0.1.0

- 23 SBOSS business ID validators covering Armenian + Russian
  + AI/config (full list in the [validators
  page](https://armosphera.github.io/A1-Validator/validators/)).
- CLI + HTTP service + library.
- 469 tests pass, 86% coverage.
- Docker image (28MB, amd64, non-root, tini, healthcheck-ready).
- CI (3 py versions, ruff, mypy, coverage gate).
- Docs site (mkdocs-material).
- 5 publish workflows (TestPyPI, GHCR, GitHub Pages, Dependabot,
  dependabot-renovate).

## Known gaps (next steps)

1. **TestPyPI trusted publisher setup** — requires a one-time
   click at https://test.pypi.org/manage/account/publishing/ (add
   owner=`Armosphera`, repo=`A1-Validator`, workflow
   filename=`publish-testpypi.yml`, environment=`testpypi`).
2. **Multi-arch Docker (amd64 + arm64)** — deferred to v0.2.0;
   see [Known issues](CHANGELOG.md#known-issues).
3. **Multi-environment PyPI publishing** — only TestPyPI is
   wired up. Production PyPI would need a separate workflow +
   trusted publisher.

## Architecture

```
autoresearch-sboss (23 examples @ 100% baseline)
  ├── A1-Localization-AM → 7 files
  ├── A1-Localization-RU → 5 files
  └── A1-AI-Core        → 7 files
        ↓
   a1_validator (single Python package, 53 public symbols)
        ↓
   ┌────────┬──────────┐
   │  CLI   │   HTTP   │
   └────────┴──────────┘
        ↓
   PyPI + GHCR + GitHub Pages
```

Each validator is a vendored port with its own test cases that
match the JavaScript source 100%. The framework is the
[autoresearch-sboss examples
directory](https://github.com/Armosphera/autoresearch-sboss/tree/main/examples)
where the same validator code has the eval contract and a
research charter (`program.md`) for further improvement.

## Credit

- **Original sources**: [A1-Localization-AM](https://github.com/Armosphera/A1-Localization-AM),
  [A1-Localization-RU](https://github.com/Armosphera/A1-Localization-RU),
  [A1-AI-Core](https://github.com/samstep74/A1-AI-Core)
  (all MIT upstream).
- **Framework**: [autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss)
  (Karpathy-style [autoresearch](https://github.com/karpathy/autoresearch)
  adapted for SBOSS).
- **License**: Armosphera Proprietary (this distribution).
