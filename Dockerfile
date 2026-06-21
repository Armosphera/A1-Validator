# syntax=docker/dockerfile:1.7
#
# Multi-stage build for a1-validator.
#
# Stage 1 (builder) — python:3.12-alpine, copy the pre-built wheel from the
#                     build context (CI runs `python -m build --sdist --wheel`
#                     first, then COPYs the artifacts in), install with the
#                     [server] extra into a clean prefix, and trim
#                     unnecessary files (pip, .pyc, __pycache__, dist-info).
# Stage 2 (runtime) — python:3.12-alpine, non-root user, tini as PID 1, copy
#                     site-packages + entry points, EXPOSE 8000, ENTRYPOINT
#                     a1-validate, CMD `serve --host 0.0.0.0 --port 8000`.
#
# Final image target: < 200MB. Alpine's musl libc + pre-built wheels for
# our dep tree (pydantic-core, uvloop, httptools, watchfiles) work
# cleanly, so we don't lose any functionality vs the debian-slim variant
# and we save ~180MB on the base image.
#
# Why a pre-built wheel (not building inside the container): the CI
# workflow runs `python -m build --sdist --wheel` BEFORE invoking docker
# build, so the artifact under ./dist/ is the source of truth. Running
# `pip wheel` again inside the builder would re-do work and produce a
# wheel whose filename doesn't match the version tag (CI gates on
# tag = wheel filename).
#
# Note on the [server] extra: the runtime image installs `a1-validator[server]`
# so the `a1-validate serve` entry point (which depends on fastapi/uvicorn) is
# available. Core-only consumers who want a lighter image can override the
# `PIP_EXTRA` build-arg (e.g. `--build-arg PIP_EXTRA=` for empty extra).
#
# Build locally:
#     docker build -t a1-validator:test .
# Build against pre-built artifacts:
#     docker build -t a1-validator:v0.1.0 \
#         --build-arg VERSION=0.1.0 \
#         --build-arg WHEEL=dist/a1_validator-0.1.0-py3-none-any.whl \
#         .

ARG PYTHON_VERSION=3.12
ARG PYTHON_IMAGE=python:${PYTHON_VERSION}-alpine

# -----------------------------------------------------------------------------
# Stage 1 — builder
# -----------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

ARG VERSION=0.1.0
# Extra to install — defaults to [server] (runtime needs fastapi/uvicorn).
# Pass `--build-arg PIP_EXTRA=` (empty) for the core package only.
ARG PIP_EXTRA=[server]

WORKDIR /build

# Build the wheel + sdist from the source tree, then install into a clean
# prefix. This makes the Dockerfile self-contained: no pre-built artifact
# in the build context, no CI coupling. The build step uses the same
# `python -m build` that the publish-testpypi workflow uses, so the wheel
# shipped in the image is byte-identical to the one on TestPyPI.
# Split COPYs (not a multi-source `COPY a b ./`) — the multi-source form
# confuses buildx's cache-key computation with a spurious "README.md not
# found" error.
COPY pyproject.toml ./
COPY README.md ./
COPY src ./src
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /wheels \
    && pip install --no-cache-dir \
        --prefix=/install \
        --break-system-packages \
        "/wheels/a1_validator-${VERSION}-py3-none-any.whl${PIP_EXTRA}" \
    && find /install -depth \
        -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /install -type f -name '*.pyc' -delete 2>/dev/null || true \
    && find /install -type d -name 'pip*' -exec rm -rf {} + 2>/dev/null || true \
    && find /install -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf /install/bin/pip* /install/bin/wheel* /install/bin/easy_install* 2>/dev/null || true


# -----------------------------------------------------------------------------
# Stage 2 — runtime
# -----------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

ARG VERSION=0.1.0

# Install tini (PID 1) + ca-certificates (HTTPS validation). Alpine uses
# `apk add` instead of `apt-get install`. Versions are pinned for
# reproducible builds (hadolint DL3018).
RUN apk add --no-cache \
        tini=0.19.0-r3 \
        ca-certificates=20260611-r0 \
    && update-ca-certificates

# Non-root user — UID/GID 10001 to avoid collisions with host UIDs.
RUN addgroup -S -g 10001 a1 \
    && adduser  -S -u 10001 -G a1 -h /app -s /sbin/nologin a1

# Copy the prepped site-packages from the builder (already trimmed).
COPY --from=builder /install /usr/local

WORKDIR /app

# Metadata.
LABEL org.opencontainers.image.title="a1-validator" \
      org.opencontainers.image.description="23 SBOSS sovereign business ID validators — HTTP service + CLI" \
      org.opencontainers.image.source="https://github.com/Armosphera/A1-Validator" \
      org.opencontainers.image.licenses="Armosphera-Proprietary" \
      org.opencontainers.image.version="${VERSION}"

USER a1

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    A1_VALIDATOR_VERSION="${VERSION}"

# tini as PID 1 — handles SIGTERM/SIGINT correctly so docker stop doesn't
# leave uvicorn orphaned. ENTRYPOINT a1-validate, CMD defaults to serve.
ENTRYPOINT ["/sbin/tini", "--", "a1-validate"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]

# Smoke-check the install (fast — runs at build time, not runtime). Catches
# obvious "image built but a1-validate is broken" regressions.
RUN a1-validate --version \
    && a1-validate list > /dev/null
