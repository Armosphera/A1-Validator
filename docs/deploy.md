# Deploy

This page covers install recipes for downstream consumers — PyPI, the
optional HTTP-service extra, and containerized deployment.

## PyPI install

```bash
# Core library only — no FastAPI, no uvicorn.
pip install a1-validator

# With the FastAPI HTTP service stack.
pip install "a1-validator[server]"

# Everything (currently identical to [server] — placeholder for future
# extras like `dev`, `docs`, `data`).
pip install "a1-validator[all]"
```

Python `>=3.10` is required. Tested against 3.10, 3.11, 3.12 in CI
(see `.github/workflows/ci.yml`).

## Version pinning

The library is on `0.1.x` — semver-ish but pre-1.0, so minor versions
may include behavior changes. Pin to the minor for reproducible
deploys:

```bash
pip install "a1-validator>=0.1,<0.2"
```

## Containerized HTTP service

Minimal `Dockerfile`:

```dockerfile
FROM python:3.12-slim

# Only the [server] extra — keeps the image small (no docs tooling, no
# pytest, no ruff/mypy).
RUN pip install --no-cache-dir "a1-validator[server]"

# Run as a non-root user.
RUN useradd --create-home --uid 1000 a1
USER a1
WORKDIR /home/a1

EXPOSE 8000
# Same import string the CLI uses internally — single source of truth.
CMD ["uvicorn", "a1_validator.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Build and run:

```bash
docker build -t a1-validator:0.1.0 .
docker run --rm -p 8000:8000 a1-validator:0.1.0
# → uvicorn running on http://0.0.0.0:8000
```

For multi-worker setups, front the container with a reverse proxy
(nginx, Caddy, Cloudflare Tunnel) for TLS termination and rate limiting.

## Gunicorn + uvicorn workers

`uvicorn[standard]` is the supported entrypoint, but gunicorn's
`uvicorn.workers.UvicornWorker` works too:

```bash
pip install "a1-validator[server]" gunicorn
gunicorn a1_validator.server:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

## Health checks

The HTTP service exposes `GET /` (returns `{name, version, validators}`)
which is a cheap health probe — `curl --fail http://host:8000/` is
enough for Kubernetes liveness/readiness without touching any validator.

For heavier probes that actually exercise a validator, use the
`/validate/hhvh` endpoint with a known-good input:

```bash
curl --fail http://host:8000/validate/hhvh \
  -H 'Content-Type: application/json' \
  -d '{"value": "00123456"}' | jq -e '.ok == true'
```

## Publishing to PyPI

The package is pure-Python with `setuptools.build_meta` — no compiled
extensions. The recommended publish flow:

```bash
# Build sdist + wheel into dist/
python -m pip install --upgrade build twine
python -m build

# Upload to PyPI (CI does this on a tag, see .github/workflows/publish.yml
# once that workflow lands — for now manual uploads).
python -m twine upload dist/*
```

The vendored `_vendored/*.json` files (chart-of-accounts, regions,
etc.) are declared as `package_data` in `pyproject.toml` so they ship
inside the wheel under `a1_validator/_vendored/`. If you vendor this
package into a downstream image, no extra steps are needed.

## See also

- :material-rocket-launch: [Validators reference](validators.md) — the
  per-kind input / output contract.
- :material-console: [CLI docs](cli.md) — `a1-validate` for one-shot
  validation, batch runs, and `serve`.
- :material-cloud: [HTTP service docs](http.md) — the FastAPI app and
  OpenAPI schema.
