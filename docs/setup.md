# Setup — publishing to TestPyPI / PyPI

The publish workflow is fully automated on every `v*` tag push, but it
needs a PyPI API token to authenticate. This is a **one-time setup**
that takes ~2 minutes:

## Step 1 — Create a PyPI account (if you don't have one)

If you don't have a PyPI account yet, register at:
- **TestPyPI:** https://test.pypi.org/account/register/
- **PyPI:** https://pypi.org/account/register/

You'll need to verify your email before the next step.

## Step 2 — Create a project-scoped API token

PyPI lets you create tokens scoped to a single project. This is the
right scope — even a compromised token can't touch other projects.

1. Go to https://test.pypi.org/manage/account/token/ (or https://pypi.org/manage/account/token/ for production)
2. Click **"Add API token"**
3. **Token name:** `github-actions-a1-validator` (anything descriptive)
4. **Scope:** `Project: a1-validator` (only this project)
5. Click **"Add"**
6. **Copy the token** — it starts with `pypi-` and you only see it once

⚠️ The token is shown only once. Copy it now; if you lose it you'll
have to generate a new one.

## Step 3 — Run the setup script

```bash
# TestPyPI:
./scripts/setup_pypi_token.sh pypi-AgEIcHlwaS5vcmcCJDk0ZjE... test

# Production PyPI (only when ready for a real release):
./scripts/setup_pypi_token.sh pypi-AgEIcHlwaS5vcmcCJDk0ZjE... prod
```

The script:
1. Verifies the token works against PyPI's JSON API (HTTP 200 or 404
   both indicate the token is valid; 401/403 means bad token/scope).
2. Stores the token as a GitHub Actions secret, scoped to the
   `testpypi` (or `prod`) environment, via `gh secret set`.
3. Verifies the secret was set.

## Step 4 — Push a tag to publish

```bash
# Tag and push — the workflow auto-fires:
git tag v0.1.0
git push origin v0.1.0

# Watch the publish workflow:
gh run watch
```

When the workflow finishes, your package is on TestPyPI. Verify it installs:

```bash
# IMPORTANT: prod PyPI as PRIMARY, TestPyPI as EXTRA. TestPyPI is
# a sandbox with arbitrary uploads (including broken name-squats
# like a broken 'fastapi' upload). Prod-first = prod deps, the
# package from TestPyPI. See README.md for the full rationale.
pip install --index-url https://pypi.org/simple/ \
            --extra-index-url https://test.pypi.org/simple/ \
            "a1-validator[server]"

# Smoke-test the CLI
a1-validate list
/tmp/a1-test/bin/a1-validate hhvh 00123456

# Or the HTTP service
/tmp/a1-test/bin/a1-validate serve --port 8000
```

## Why not OIDC trusted publishing?

PyPI's OIDC trusted publishing lets GitHub Actions publish to PyPI
without a token — but the setup step requires a one-time web UI
registration that **can't be scripted** (browser + 2FA required).

API tokens trade that one-time web step for a one-time terminal
command. Same security model (project-scoped, revocable from PyPI
or GitHub), and the rest of the workflow is identical.

If/when PyPI adds a public API for trusted-publisher registration,
the workflow can switch back to OIDC. For now, the token path is
the realistic automation boundary.

## Revoking a token

If the token is compromised:
1. Go to https://test.pypi.org/manage/account/token/ (or PyPI prod)
2. Find the token, click **"Remove"**
3. Run the setup script again with a new token

To rotate the GitHub-side secret:
```bash
./scripts/setup_pypi_token.sh pypi-NEW-TOKEN test
```
