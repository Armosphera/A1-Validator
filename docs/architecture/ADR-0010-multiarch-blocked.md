# ADR-0010 — Multi-arch Docker state for A1-Validator

> **Status:** Accepted (deferred to
> v0.3.0; blocked on upstream bug).
> **Date:** 2026-06-21.
> **Authors:** mavis (drafted per
> plan 66 W66-2 deliverable).
> **Supersedes:** nothing.
> **Superseded by:** nothing.
> **Related:** [ADR-0008 — External
> signing for non-repudiable audit
> evidence](https://github.com/Armosphera/A1-AI-ERP-SBOS-MSTUDIO-sovereign/blob/main/docs/architecture/ADR-0008-external-signing.md);
> the A1-Validator v0.1.0 / v0.1.13
> Docker story (commits
> `be7629b` + `d8f7a08`); plan 64
> W64-1 (v0.2.0 version-bump
> release).

---

## 1. Context

The A1-Validator `publish-ghcr.yml`
workflow (`.github/workflows/publish-ghcr.yml`)
ships a Docker image to GHCR on
every `v*` tag push. The current
implementation uses **plain
`docker build`** (single-arch
linux/amd64) — not `docker buildx`
with multi-platform support.

The reason is a docker/buildx
cache-key computation bug that
surfaced in the v0.1.0 work:
multi-platform builds with
buildkit's `docker` driver (the
default) intermittently fail
with a "not found" error on
`COPY` steps, even when the
input files are present in the
build context. The bug is
documented in v0.1.0's
"Known Issues" section of the
CHANGELOG and in a comment in
`publish-ghcr.yml` (lines 37-44).

The bug is upstream in
`docker/buildkit`; the SBOSS
sovereign monorepo has the
same issue (see the W54-1
undici-7.28.0 cherry-pick
memory entry for the
`docker/buildx` cache-key
behavior in a related
context).

v0.1.0 shipped single-arch
amd64 with the workaround
(plain `docker build` + a
simplified `.dockerignore` that
removes the `*.md / !README.md`
exception pattern that
triggered the bug). v0.2.0
(plan 64 W64-1) was a
version-bump release with no
code change; multi-arch is
deferred.

## 2. Decision

**Defer multi-arch Docker
(linux/amd64 + linux/arm64) to
v0.3.0 or later.** v0.2.0 ships
single-arch amd64 with the
existing workaround. v0.3.0
will re-enable multi-arch when
the upstream docker/buildx
cache-key bug is fixed (track
https://github.com/moby/buildkit
and https://github.com/docker/buildx).

The A1-Validator will continue
to support `linux/amd64` only
in the published image. ARM64
users (Apple Silicon laptops,
AWS Graviton instances) can
build from source using the
`Dockerfile` in the repo; the
build will work but is not
published to GHCR.

## 3. Consequences

**Negative consequences:**

- **ARM64 users cannot pull a
  pre-built A1-Validator image
  from GHCR.** They must build
  from source, which is a
  non-trivial setup (Python
  3.12, the `a1-validator`
  build context, the `[server]`
  extra for the HTTP service).
  This affects Apple Silicon
  developers (M1/M2/M3 Macs)
  and AWS Graviton
  production deploys.

- **No `linux/arm64/v8` manifest
  entry in the GHCR image.**
  Manifest tools like
  `docker manifest inspect` will
  show only the amd64 entry.

- **No multi-arch CI
  verification.** The CI
  doesn't exercise an ARM64
  build; ARM64-specific
  bugs (e.g., musl libc
  differences in Alpine) would
  not be caught before a release.

**Positive consequences:**

- **Single-arch build is fast
  and reliable.** v0.1.0's
  plain `docker build` is
  ~28MB and ~2 minutes; no
  cache-key races.

- **No v0.2.0 blocker.** v0.2.0
  is purely a version-bump +
  CHANGELOG release. The
  multi-arch carry-forward is
  explicitly tracked in the
  v0.2.0 CHANGELOG.

- **Simpler operator
  experience.** The current
  single-arch build doesn't
  require buildkit, buildx, or
  manifest-tool. The operator
  pulls the image with
  `docker pull ghcr.io/...` and
  it works on amd64 Linux.

## 4. Workaround attempts considered

### 4.1 docker-container driver (rejected)

The `docker buildx build
--driver docker-container` uses
a running buildkit container
directly (without the docker
driver's cache-key code path).
This is a known workaround for
the cache-key bug. Tested in
the v0.1.0 work; **still
exhibits the same bug** for
multi-platform builds because
the cache-key computation is
in buildkit, not the driver.

### 4.2 manifest-tool approach (rejected)

Build amd64 + arm64 as
**separate single-platform
images**, then combine with
`manifest-tool` to create a
multi-arch manifest. This
avoids the multi-platform
buildx call entirely.

**Rejected** because:
1. Requires two separate CI
   jobs (amd64 + arm64) which
   roughly doubles the CI
   runtime.
2. The arm64 job requires
   QEMU emulation (the GHCR
   runners are amd64) or a
   native arm64 runner
   (GitHub-hosted arm64
   runners are in preview; not
   GA at the time of this
   ADR).
3. The QEMU emulation adds
   ~5x build time to the arm64
   job, making the total
   CI runtime worse than the
   current single-arch build.

### 4.3 Buildkit directly (rejected)

Run buildkit as a sidecar
container in the CI job and
build with `buildctl`. This
bypasses the docker buildx
cache-key code path entirely.

**Rejected** because:
1. The cache-key bug is in
   buildkit's own cache-key
   computation, not just the
   docker driver's. Direct
   buildkit calls have the same
   intermittent failure.
2. The Dockerfile syntax
   requires translation (some
   Dockerfile directives are
   docker-specific, not
   buildkit-generic).

### 4.4 Ship amd64 only (accepted)

Use plain `docker build` (no
buildx) with single-arch amd64.
The .dockerignore is simplified
(no `!pattern` exceptions).
This is what v0.1.0 + v0.2.0
ships.

**Accepted** because:
1. The build is fast (~2
   minutes) and reliable.
2. The image is small (~28MB).
3. ARM64 users can build from
   source; the operator can
   decide whether to add
   arm64 build instructions
   to the README in a future
   release.

## 5. Re-evaluation criteria

This ADR will be **superseded**
when ALL of the following are
true:

1. The docker/buildx
   cache-key bug is fixed
   upstream (track
   https://github.com/moby/buildkit
   + https://github.com/docker/buildx
   for a release that fixes
   the bug).
2. The A1-Validator `.dockerignore`
   can be made buildx-friendly
   without the `!pattern`
   exception pattern.
3. The A1-Validator `Dockerfile`
   is compatible with the
   multi-platform buildx call
   (`docker buildx build
   --platform linux/amd64,linux/arm64`).
4. CI has native arm64
   runner support OR QEMU
   emulation is fast enough
   that the multi-arch CI
   runtime is acceptable.

When these are met, ship a
new v0.x release with
multi-arch support. The
`publish-ghcr.yml` workflow
becomes:

```yaml
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3

- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and push (multi-arch)
  uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    platforms: linux/amd64,linux/arm64
    tags: ${{ steps.meta.outputs.tags }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## 6. Workaround for ARM64 users (today)

ARM64 users can build from
source:

```bash
git clone https://github.com/Armosphera/A1-Validator
cd A1-Validator
docker build \
  --tag a1-validator:local \
  --build-arg VERSION=local \
  .
```

The build will work on an
ARM64 host (no buildx needed;
plain `docker build` honors
the host architecture
automatically). The image is
local-only; it's not pushed
to GHCR.

For production deploys on
ARM64 (e.g., AWS Graviton),
the operator should build the
image in their CI/CD pipeline
or use a native arm64 build
environment. The Dockerfile is
arch-agnostic; the build
succeeds on both amd64 and
arm64 hosts.

## 7. Decision

**Defer multi-arch Docker to
v0.3.0 or later. v0.2.0 ships
single-arch amd64 with the
plain-`docker-build` workaround.
Track the upstream docker/buildx
cache-key bug for re-evaluation
when fixed.**

The A1-Validator team will
re-evaluate this ADR when the
upstream bug is fixed. The
re-evaluation trigger is
**NOT operator-driven**; it
happens when the upstream bug
is fixed. Plan 67+ will pick
up the re-evaluation if/when
the trigger fires.
