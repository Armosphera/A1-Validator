#!/usr/bin/env bash
# scripts/check_pypi_oidc_readiness.sh
#
# W66-3 — pre-flight check for the
# PyPI trusted-publisher migration
# (ADR-0011). This script does NOT
# register the trusted publisher
# (that requires the 2FA web step
# at PyPI). It only verifies the CI
# side is ready to accept the OIDC
# token once the operator does the
# 2FA step.
#
# Checks:
# 1. .github/workflows/publish-testpypi.yml
#    has the `id-token: write`
#    permission.
# 2. The workflow uses
#    `pypa/gh-action-pypi-publish@release/v1`
#    or newer (with no `password:`
#    kwarg).
# 3. The action version is recent
#    enough to support OIDC
#    (v1.4+).
#
# Usage:
#   ./scripts/check_pypi_oidc_readiness.sh
#
# Exit code:
#   0 = all checks pass (CI is
#       ready for OIDC; operator can
#       do the 2FA web step at PyPI)
#   1 = one or more checks fail
#       (CI is NOT ready; the OIDC
#       migration would fail)
#
# After the operator does the 2FA
# web step at PyPI:
# 1. Edit .github/workflows/publish-testpypi.yml
#    to remove the `password:` env
#    var (the workflow already uses
#    `pypa/gh-action-pypi-publish@release/v1`
#    which auto-detects OIDC when
#    `id-token: write` is set).
# 2. Push a v* tag and verify
#    TestPyPI publish via OIDC
#    succeeds.
# 3. Rotate + revoke the old
#    API token at PyPI.
# 4. Mark this ADR as superseded
#    (v0.3.0 release).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/publish-testpypi.yml"

if [[ ! -f "$WORKFLOW" ]]; then
    echo "ERROR: $WORKFLOW not found"
    echo "       Run this script from the repo root."
    exit 1
fi

echo "W66-3 — PyPI OIDC readiness check"
echo "==================================="
echo ""

# Check 1: id-token: write permission
if grep -q "id-token: write" "$WORKFLOW"; then
    echo "  [OK]    id-token: write permission is set"
else
    echo "  [FAIL]  id-token: write permission is NOT set"
    echo "          The workflow cannot mint OIDC tokens without this."
    echo "          Add this to the workflow's permissions block:"
    echo "            permissions:"
    echo "              id-token: write"
    echo "              contents: read"
    EXIT=1
fi

# Check 2: uses pypa/gh-action-pypi-publish (in a real `uses:` line, not a comment)
# Match "uses: pypa/gh-action-pypi-publish@..." in the actual step list
# (anchored to start-of-line + optional whitespace + "uses:").
if grep -qE "^\s*uses:\s*pypa/gh-action-pypi-publish@" "$WORKFLOW"; then
    echo "  [OK]    uses pypa/gh-action-pypi-publish"
else
    echo "  [FAIL]  does not use pypa/gh-action-pypi-publish in a 'uses:' step"
    echo "          The OIDC auto-detect requires pypa/gh-action-pypi-publish@release/v1 (or v1.4+ on @v1)."
    echo "          The current workflow uses twine (which doesn't auto-detect OIDC)."
    echo "          The OIDC migration replaces the twine step with:"
    echo "            - uses: pypa/gh-action-pypi-publish@release/v1"
    echo "              with:"
    echo "                repository-url: https://test.pypi.org/legacy/"
    EXIT=1
fi

# Check 3: action version is release/v1 or newer
if grep -qE "pypa/gh-action-pypi-publish@(release/v1|@v[1-9])" "$WORKFLOW"; then
    echo "  [OK]    action version is release/v1 or newer"
else
    echo "  [WARN]  action version may be older than release/v1"
    echo "          OIDC support is reliable on release/v1 (or v1.4+ on @v1)."
    echo "          Consider upgrading the action version."
fi

# Check 4: no `password:` kwarg in the publish step
if grep -qE "^\s*password:" "$WORKFLOW"; then
    echo "  [FAIL]  password: kwarg is still set"
    echo "          The OIDC migration removes this kwarg; the OIDC"
    echo "          token is auto-detected from id-token: write."
    EXIT=1
else
    echo "  [OK]    no password: kwarg (ready for OIDC)"
fi

echo ""
if [[ "${EXIT:-0}" -eq 0 ]]; then
    echo "RESULT: all checks pass — CI is ready for OIDC."
    echo ""
    echo "Next steps for the operator:"
    echo "  1. Log in to PyPI in a browser."
    echo "  2. Navigate to the A1-Validator project page."
    echo "  3. Go to 'Publishing' -> 'Add a new pending publisher'."
    echo "  4. Fill in:"
    echo "       PyPI Project: a1-validator"
    echo "       Owner: Armosphera"
    echo "       Repository name: A1-Validator"
    echo "       Workflow filename: publish-testpypi.yml"
    echo "       Environment name: testpypi"
    echo "  5. Confirm with 2FA."
    echo "  6. Tell the maintainers 'trusted publisher registered'."
    echo "  7. The maintainers will then:"
    echo "     a. Edit .github/workflows/publish-testpypi.yml to remove"
    echo "        the password: env var (if any)."
    echo "     b. Push a v* tag and verify TestPyPI publish via OIDC."
    echo "     c. Rotate + revoke the old API token at PyPI."
    echo "     d. Mark ADR-0011 as superseded (v0.3.0 release)."
else
    echo "RESULT: one or more checks failed."
    echo ""
    echo "Fix the failing checks above before the operator does"
    echo "the 2FA web step at PyPI. Otherwise the OIDC migration"
    echo "will fail at first publish."
fi

exit "${EXIT:-0}"
