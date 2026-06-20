# Deployment guide

This document covers:

1. Pulling and running the published Docker image from GHCR.
2. Publishing a new version of `a1-validator` (TestPyPI + GHCR).

The two CI workflows in `.github/workflows/` do the publishing work —
pushing a tag is all an operator needs to do.

---

## 1. Pulling and running the Docker image

The package is published to **GitHub Container Registry** at
`ghcr.io/armosphera/a1-validator`. The image bundles the FastAPI HTTP
service (`a1-validate serve`) under `tini` as PID 1 and listens on
port `8000`.

### Quick start (docker run)

```bash
# Pull the latest v0.1.x release.
docker pull ghcr.io/armosphera/a1-validator:v0.1.0

# Run the HTTP service on port 8000.
docker run --rm -p 8000:8000 ghcr.io/armosphera/a1-validator:v0.1.0

# In another terminal:
curl http://localhost:8000/                    # discovery JSON
curl http://localhost:8000/validators          # 23-validator list
curl -X POST http://localhost:8000/validate/hhvh \
     -H 'content-type: application/json' \
     -d '{"value":"00123456"}'                 # {"ok": true, "normalized": "00123456", ...}
```

### docker compose

```bash
# Default — boots v0.1.0 on port 8000.
docker compose up -d
docker compose logs -f

# Different version / port / log level:
A1_VALIDATOR_VERSION=v0.1.1 \
A1_VALIDATOR_PORT=9000 \
A1_VALIDATOR_LOG_LEVEL=debug \
  docker compose up -d
```

The compose file pins to a specific version (no `:latest`). This is
intentional — production deployments should pin by tag (or by digest —
see "pin by digest" below). `A1_VALIDATOR_VERSION=v0.1.1` lets you
upgrade with a single env-var change.

### Pin by digest (production)

Image tags can be moved; digests can't. For production, pin to the
SHA256 of the image you validated:

```bash
# Get the digest for a tag:
docker buildx imagetools inspect ghcr.io/armosphera/a1-validator:v0.1.0 \
  --format '{{json .Manifest}}' | jq -r .digest

# Pin in docker-compose.yml:
#   image: ghcr.io/armosphera/a1-validator@sha256:<digest>
```

### Inspecting the image

```bash
docker run --rm ghcr.io/armosphera/a1-validator:v0.1.0 --help
docker run --rm ghcr.io/armosphera/a1-validator:v0.1.0 list
docker run --rm ghcr.io/armosphera/a1-validator:v0.1.0 hhvh 00123456
```

The image's `ENTRYPOINT` is `a1-validate`, so any CLI subcommand works
through `docker run` — not just `serve`.

### Image properties

| Property            | Value                                                    |
|---------------------|----------------------------------------------------------|
| Base image          | `python:3.12-slim`                                       |
| Image size          | ~180 MB (target: < 200 MB)                               |
| User                | non-root (`a1`, UID/GID 10001)                           |
| PID 1               | `tini` (forwards signals, reaps zombies)                 |
| Default port        | `8000`                                                   |
| Default command     | `a1-validate serve --host 0.0.0.0 --port 8000`           |
| Env vars (consumed) | `A1_VALIDATOR_VERSION`, `A1_VALIDATOR_LOG_LEVEL`, `A1_VALIDATOR_WORKERS` |
| Platforms           | `linux/amd64`, `linux/arm64`                             |

### Reverse proxy / TLS

The container exposes plain HTTP. For TLS termination, run behind a
reverse proxy (nginx, Caddy, traefik, Cloudflare Tunnel, …) and proxy
`/` to the container's port 8000. Example nginx server block:

```nginx
server {
    listen 443 ssl;
    server_name validator.example.com;

    ssl_certificate     /etc/letsencrypt/live/validator.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/validator.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 2. Publishing a new version

The CI pipeline handles TestPyPI + GHCR publishing automatically. The
operator's job is to (1) bump the version in `pyproject.toml` /
`src/a1_validator/__init__.py`, (2) push a tag, (3) watch the
workflows.

### Pre-flight checklist

- [ ] `pyproject.toml` `version = "X.Y.Z"` matches.
- [ ] `src/a1_validator/__init__.py` `__version__ = "X.Y.Z"` matches.
- [ ] `CHANGELOG.md` (if maintained) has an entry for the new version.
- [ ] All tests green on `main` (`pytest tests/ -v` locally, or wait
      for CI on the merged PR).
- [ ] You have push rights to `origin` and `tags`.

### Cut a tag

```bash
# On the main branch, with all changes merged in:
git checkout main
git pull --ff-only origin main

# Make sure the working tree is clean.
git status

# Tag with the leading 'v' — the GitHub Actions workflows match on `v*`.
# The Docker image tag strips the 'v' automatically (:0.1.0, not :v0.1.0).
git tag -a v0.1.1 -m "Release 0.1.1 — <one-line summary>"

# Push the tag. THIS triggers BOTH publishing workflows.
git push origin v0.1.1
```

### What happens on `git push origin vX.Y.Z`

Two GitHub Actions workflows fire (in parallel):

| Workflow                                | Trigger                   | Outcome                                                  |
|-----------------------------------------|---------------------------|----------------------------------------------------------|
| `.github/workflows/publish-testpypi.yml`| `v0.1.0*` tag push (safety scope — see below) | Builds sdist+wheel, uploads to TestPyPI. |
| `.github/workflows/publish-ghcr.yml`    | Any `v*` tag push         | Multi-arch (amd64+arm64) image, pushes to GHCR. |

#### TestPyPI safety scope — `v0.1.0*` only

The TestPyPI workflow currently only triggers on `v0.1.0*` tags. This
is a deliberate safety scoping — TestPyPI accepts anonymous uploads
for first-time publishers, and we want to keep the publishing pipeline
narrow while we shake it out. To widen the scope once `v0.1.1+`
lands, edit `.github/workflows/publish-testpypi.yml` and change:

```yaml
tags:
  - "v0.1.0*"   # <-- change to "v*" once v0.1.1+ is ready
```

The required `TESTPYPI_API_TOKEN` secret must be configured in
**Settings → Secrets and variables → Actions → Repository secrets**
before the first publish. Generate the token at
https://test.pypi.org/manage/account/token/ with the
"Project: a1-validator" scope.

#### GHCR — `v*`

The GHCR workflow runs on every `v*` tag. No secrets to configure —
the default `GITHUB_TOKEN` already has `packages: write` permission
on first-party repos. Image visibility is **public** by default for
GitHub-Actions-built images; if you want the package private, change
its visibility on the package settings page after the first push.

### Post-publish verification

```bash
# 1. TestPyPI — should show the new version within ~30s.
open https://test.pypi.org/project/a1-validator/

# 2. Install from TestPyPI to verify the artifact:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            a1-validator==0.1.1
python -c "import a1_validator; print(a1_validator.__version__)"

# 3. GHCR — image should appear in the registry within ~3min (multi-arch
#    builds take longer than single-arch).
docker pull ghcr.io/armosphera/a1-validator:v0.1.1
docker run --rm ghcr.io/armosphera/a1-validator:v0.1.1 --version

# 4. Run the full smoke suite against the new image:
docker run --rm -p 8000:8000 ghcr.io/armosphera/a1-validator:v0.1.1 &
sleep 2
curl -fsS http://localhost:8000/ | python -m json.tool
curl -fsS http://localhost:8000/validators | python -m json.tool | head
curl -fsS -X POST http://localhost:8000/validate/hhvh \
     -H 'content-type: application/json' \
     -d '{"value":"00123456"}' | python -m json.tool
kill %1
```

### Promote TestPyPI → production PyPI

(TODO — not part of this task. The TestPyPI workflow is the only
publish-to-PyPI path; production PyPI publishing is the next milestone
once TestPyPI has been validated for a few releases.)

### Rolling back

- **Bad Docker image**: re-tag a previous known-good image as the
  current `vX.Y.Z`, or update your compose env to point at the prior
  tag. Image tags are mutable; digests are not.
- **Bad TestPyPI upload**: yank from TestPyPI web UI. The CI does not
  republish automatically.

---

## 3. Local development

For local development, install the package in editable mode rather
than using the Docker image:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
pytest -v
a1-validate --version
a1-validate serve --reload
```

To build the Docker image locally:

```bash
# 1. Build sdist + wheel (the Dockerfile expects these under ./dist/).
python -m pip install build
python -m build --sdist --wheel --outdir dist/

# 2. Build the image.
docker build -t a1-validator:test .

# 3. Smoke-test.
docker run --rm a1-validator:test --version
docker run --rm a1-validator:test list
docker run --rm -p 8000:8000 a1-validator:test
```

See `tests/test_packaging.py` for the hermetic version of this
flow (it does steps 1–2 inside a tmpdir venv so your dev env stays
clean).
