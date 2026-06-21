# ADR-0011 — PyPI trusted-publisher migration for A1-Validator

> **Status:** Accepted (deferred to
> v0.3.0; blocked on operator's
> 2FA web step).
> **Date:** 2026-06-21.
> **Authors:** mavis (drafted per
> plan 66 W66-3 deliverable).
> **Supersedes:** nothing.
> **Superseded by:** nothing.
> **Related:** [ADR-0010 — Multi-arch
> Docker state (blocked on
> upstream buildx bug)](./ADR-0010-multiarch-blocked.md);
> `scripts/setup_pypi_token.sh`
> (the current API-token setup
> script); the
> `publish-testpypi.yml` workflow
> (current publish path).

---

## 1. Context

A1-Validator publishes to PyPI
on every `v*` tag push. The
current publish path uses
**PyPI API tokens** (project-
scoped tokens stored as a
GitHub Actions environment
secret). The token is set up
once via `scripts/setup_pypi_token.sh`,
which reads the token from
stdin / env var / CLI arg and
stores it via `gh secret set`.

PyPI also supports
**trusted publishing** (OIDC),
which is the modern PyPI
recommendation:
- No long-lived token to
  manage or rotate.
- Scoped to a specific GitHub
  repo + workflow + environment.
- Credentials are short-lived
  (issued per CI run).
- No 2FA re-entry per publish
  (the 2FA is at the
  registration step, not per
  publish).

The A1-Validator v0.1.0 work
deliberately chose API tokens
over OIDC because **OIDC
registration requires a
browser + 2FA web step at
PyPI that cannot be
scripted**. The
`scripts/setup_pypi_token.sh`
was the realistic automation
boundary until PyPI adds a
public API for trusted-publisher
registration.

## 2. Decision

**Defer PyPI trusted-publisher
migration to v0.3.0 or later.**
v0.2.0 continues to use API
tokens via the existing
`scripts/setup_pypi_token.sh`
script. v0.3.0 will migrate to
OIDC when the operator does
the one-time 2FA web step at
PyPI.

The migration is **operator-
driven**, not code-driven. The
operator (the person with the
PyPI account credentials +
2FA device) must:
1. Log in to PyPI in a browser.
2. Navigate to the A1-Validator
   project page.
3. Go to "Publishing" → "Add a
   new pending publisher".
4. Fill in the GitHub repo,
   workflow filename,
   environment name (matching
   the `testpypi` environment
   in the workflow).
5. Confirm with 2FA.
6. Tell the maintainers
   "trusted publisher
   registered" so the
   workflow can be updated.

Steps 1-5 cannot be scripted;
they require browser
interaction + 2FA. Step 6 is
a single message.

## 3. Consequences

**Negative consequences:**

- **Long-lived API token
  remains in use.** The token
  is stored as a GitHub
  Actions environment secret
  (encrypted at rest) but is
  a long-lived credential that
  must be rotated periodically
  (recommended: every 90 days).
  Rotation is a manual process:
  regenerate at PyPI → re-run
  `setup_pypi_token.sh` with
  the new token.

- **Token compromise risk.**
  A compromised token (e.g.,
  via a leaked CI log or a
  malicious actor with repo
  access) could be used to
  upload malicious packages
  to PyPI under the
  A1-Validator name. The
  project-scoped token limits
  the blast radius (can't
  touch other PyPI projects),
  but it can still affect
  A1-Validator.

- **No per-publish 2FA.** The
  token bypasses PyPI's
  mandatory 2FA on publish.
  The 2FA is enforced once at
  token creation; subsequent
  publishes are silent.

**Positive consequences:**

- **No 2FA re-entry per
  publish.** The token-based
  workflow can publish on
  every tag push with no
  human interaction. The CI
  is fully automated.

- **Simpler operator
  experience today.** The
  `setup_pypi_token.sh`
  script is a 30-second
  command; OIDC requires
  the 5-step web flow above.

- **No new dependencies on
  PyPI's OIDC API.** The
  OIDC API is stable but newer
  than the token API. Tokens
  are the well-trodden path.

## 4. The OIDC migration (when triggered)

When the operator does the
2FA web step and the trusted
publisher is registered, the
migration is:

1. **Update
   `publish-testpypi.yml`** to
   use OIDC instead of the
   token:
   ```yaml
   - name: Publish to TestPyPI
     uses: pypa/gh-action-pypi-publish@release/v1
     with:
       repository-url: https://test.pypi.org/legacy/
   ```
   No `password` env var; the
   `id-token: write` permission
   on the job is sufficient.

2. **Update the GH workflow
   permissions:**
   ```yaml
   permissions:
     id-token: write
     contents: read
   ```
   (already set in v0.1.0; no
   change needed)

3. **Remove the
   `setup_pypi_token.sh` call
   from the operator's
   workflow.** The script
   becomes a historical
   artifact; future operators
   don't need it.

4. **Document the
   registration step** in
   `docs/setup.md` (or
   equivalent) so future
   operators know how to
   register a new trusted
   publisher (after PyPI
   project transfer, repo
   rename, etc.).

5. **Rotate + revoke the old
   API token** at PyPI once
   the OIDC path is verified
   working. The token is no
   longer needed; leaving it
   active is a security risk.

## 5. Re-evaluation criteria

This ADR will be **superseded**
when ALL of the following are
true:

1. The operator has completed
   the 2FA web step at PyPI
   (registered the trusted
   publisher).
2. The trusted publisher is
   verified by a successful
   TestPyPI publish via the
   OIDC path (no token).
3. The production PyPI
   trusted publisher is also
   registered (separate 2FA
   step at PyPI production).
4. The old API token is
   rotated + revoked.

When these are met, the
`publish-testpypi.yml` workflow
is updated to OIDC; the
`scripts/setup_pypi_token.sh`
script is marked as deprecated
in favor of a new
`scripts/setup_pypi_oidc.md`
(or similar) that documents
the OIDC registration.

## 6. The prep script
(`scripts/check_pypi_oidc_readiness.sh`)

This ADR ships with a small
helper script that the
operator can run **before**
doing the 2FA web step, to
verify the CI workflow is
ready for OIDC. The script
checks:

1. The `publish-testpypi.yml`
   workflow has the
   `id-token: write`
   permission.
2. The `publish-testpypi.yml`
   workflow uses
   `pypa/gh-action-pypi-publish@release/v1`
   (or newer) with no `password:`
   kwarg.
3. The `pypa/gh-action-pypi-publish`
   action version is recent
   enough to support OIDC
   (v1.4+).

The script does NOT register
the trusted publisher (that
requires the 2FA web step). It
only verifies the CI side is
ready, so the operator can do
the web step with confidence
that the CI will accept the
OIDC token.

## 7. Decision

**Defer PyPI trusted-publisher
migration to v0.3.0 or later.
v0.2.0 continues to use API
tokens via the existing
`scripts/setup_pypi_token.sh`.
The migration is operator-
driven (requires the 2FA web
step at PyPI). The
`scripts/check_pypi_oidc_readiness.sh`
helper is shipped in W66-3 to
let the operator verify the CI
side is ready before doing
the 2FA step.**

The A1-Validator team will
re-evaluate this ADR when the
operator signals the 2FA web
step is done. The re-evaluation
trigger is **operator-driven**;
it happens when the operator
says "trusted publisher
registered". Plan 67+ will
pick up the migration if/when
the trigger fires.
