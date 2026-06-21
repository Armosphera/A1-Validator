#!/usr/bin/env bash
# scripts/setup_pypi_token.sh
#
# One-time setup: register a PyPI API token as a GitHub Actions secret so
# the publish-testpypi.yml workflow can publish automatically on every
# tag push — no manual web UI, no 2FA re-entry.
#
# Why API tokens (not OIDC trusted publishing):
#   - Trusted publishing requires a one-time web UI step that requires
#     browser + 2FA. Can't be scripted cleanly.
#   - API tokens can be created in the same web UI but only ONCE, then
#     reused forever. This script makes that one-time step a 30-second
#     command.
#   - Token scope: project-only ("Upload to: a1-validator"), so even a
#     compromised token can't touch other PyPI projects.
#
# Usage:
#   ./scripts/setup_pypi_token.sh <token> [test|prod]
#
# Examples:
#   ./scripts/setup_pypi_token.sh pypi-XXXXXXXXXXXXXXXXXXXXXXXXXXXX test
#   ./scripts/setup_pypi_token.sh pypi-YYYYYYYYYYYYYYYYYYYYYYYYYYYY prod
#
# After running:
#   - TestPyPI:    ./scripts/setup_pypi_token.sh pypi-XXX test
#   - Production:  ./scripts/setup_pypi_token.sh pypi-YYY prod
#
# Then push a v* tag — the publish-testpypi.yml workflow picks up the
# token from GitHub secrets and publishes automatically.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <pypi-api-token> [test|prod]"
    echo ""
    echo "Get a token at:"
    echo "  TestPyPI:  https://test.pypi.org/manage/account/token/"
    echo "  PyPI:      https://pypi.org/manage/account/token/"
    echo ""
    echo "Scope the token to 'Project: a1-validator' (only this project)."
    exit 1
fi

TOKEN="$1"
ENVIRONMENT="${2:-test}"

case "$ENVIRONMENT" in
    test)
        REPO="https://test.pypi.org/legacy/"
        API_BASE="https://test.pypi.org/pypi"
        API_CHECK="https://test.pypi.org/simple/a1-validator/"
        SECRET_NAME="TEST_PYPI_TOKEN"
        ;;
    prod)
        REPO="https://upload.pypi.org/legacy/"
        API_BASE="https://pypi.org/pypi"
        API_CHECK="https://pypi.org/simple/a1-validator/"
        SECRET_NAME="PYPI_TOKEN"
        ;;
    *)
        echo "Unknown environment: $ENVIRONMENT (expected 'test' or 'prod')"
        exit 1
        ;;
esac

# ----- Sanity check the token -----
echo "Verifying token against ${API_BASE}/a1-validator/json …"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${API_BASE}/a1-validator/json" || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
    # 200 = project exists, 404 = project doesn't exist yet (which is fine
    # for a first publish). 401/403 = bad token.
    echo "  ✓ token is valid (HTTP $HTTP_CODE — OK either way)"
else
    echo "  ✗ token rejected (HTTP $HTTP_CODE). Double-check the value + scope."
    exit 1
fi

# ----- Find the GH repo from CWD or remotes -----
if ! gh repo view --json name >/dev/null 2>&1; then
    echo ""
    echo "ERROR: 'gh repo view' failed. Make sure you're inside the A1-Validator"
    echo "       repo directory and that 'gh auth status' is logged in."
    exit 1
fi

REPO_SLUG=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Setting secret $SECRET_NAME on $REPO_SLUG (environment=$ENVIRONMENT) …"

echo "$TOKEN" | gh secret set "$SECRET_NAME" \
    --repo "$REPO_SLUG" \
    --env "$ENVIRONMENT" \
    --body -

# ----- Confirm -----
echo ""
echo "Verifying secret was set …"
SET_COUNT=$(gh secret list --repo "$REPO_SLUG" --env "$ENVIRONMENT" --json name -q '.[] | select(.name=="'"$SECRET_NAME"'") | .name' | wc -l | tr -d ' ')
if [ "$SET_COUNT" -ge 1 ]; then
    echo "  ✓ $SECRET_NAME is set in the '$ENVIRONMENT' environment"
else
    echo "  ✗ $SECRET_NAME does not appear in the '$ENVIRONMENT' environment"
    exit 1
fi

echo ""
echo "✓ Setup complete. To publish:"
echo "    git tag v0.X.Y && git push origin v0.X.Y"
echo ""
echo "  The publish-testpypi.yml workflow will fire, use the token to"
echo "  authenticate with $REPO, and upload the sdist + wheel."
