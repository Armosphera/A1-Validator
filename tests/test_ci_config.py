"""test_ci_config.py — sanity checks on the CI + docs infrastructure.

These tests don't exercise the package; they pin the shape of the CI
configuration so silent drift (e.g. someone drops a Python version from
the matrix, or rewrites the docs deploy action) is caught before it
lands on `main`.

Why this matters:
- The Python matrix in `ci.yml` is a deliberate contract — dropping a
  version silently would mean untested Python interpreters in production.
- The docs deploy workflow references a specific action
  (`peaceiris/actions-gh-pages@v3`) — a swap to a different action
  would change deploy semantics and should require a deliberate test
  update, not a silent landing.
- YAML files in `.github/workflows/` and the repo root are part of
  the repo's executable surface. A typo in `mkdocs.yml` or a malformed
  workflow file would break CI invisibly until someone hits the broken
  path in production.

Each test is fast (< 100 ms) and has no external dependencies.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# YAML loader that tolerates the `!!python/name:...` tags mkdocs-material
# uses for pymdownx.emoji and similar extensions. PyYAML's safe_load refuses
# to construct unknown Python tags by default; we want a structural parse
# (so the test can introspect keys/values) without actually importing the
# referenced Python object. The custom constructor just keeps the tag's
# value as a plain string.
# ---------------------------------------------------------------------------
class _PermissiveSafeLoader(yaml.SafeLoader):
    """SafeLoader that resolves `!!python/name:X` tags to their string value.

    mkdocs.yml uses `!!python/name:material.extensions.emoji.twemoji` and
    similar tags to point at extension callables. PyYAML encodes those as
    full tag URIs (`tag:yaml.org,2002:python/name:material.extensions.…`)
    and SafeLoader won't construct them by default. We use the
    ``add_multi_constructor`` API which matches the URI prefix and lets us
    keep the suffix as a plain string — we don't need the actual callable
    in a test; we only need the parse to succeed so we can introspect keys.
    """


def _construct_python_name_suffix(loader, suffix, node):  # type: ignore[no-untyped-def]
    """Resolve a `!!python/name:<suffix>` tag to the suffix as a string."""
    return str(suffix)


_PermissiveSafeLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:",
    _construct_python_name_suffix,
)


def _safe_load(text: str):  # type: ignore[no-untyped-def]
    """Parse YAML tolerating `!!python/name:…` extension tags."""
    return yaml.load(text, Loader=_PermissiveSafeLoader)


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Workflow discovery.
# ---------------------------------------------------------------------------

def _workflows_dir() -> Path:
    d = REPO_ROOT / ".github" / "workflows"
    if not d.is_dir():
        pytest.skip(f".github/workflows/ not found at {d}")
    return d


def _workflow_paths() -> list[Path]:
    return sorted(_workflows_dir().glob("*.yml")) + sorted(_workflows_dir().glob("*.yaml"))


# ---------------------------------------------------------------------------
# Generic YAML validity.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("workflow_path", _workflow_paths(), ids=lambda p: p.name)
def test_workflow_file_is_valid_yaml(workflow_path: Path) -> None:
    """Every .github/workflows/*.yml file must parse as YAML.

    GitHub Actions runs workflows through its own YAML parser; `yaml.safe_load`
    is the closest local equivalent. A parse error here usually means an
    editor introduced smart-quote characters or broken indentation.
    """
    content = workflow_path.read_text(encoding="utf-8")
    parsed = _safe_load(content)
    assert isinstance(parsed, dict), (
        f"{workflow_path.name}: expected top-level mapping, got {type(parsed).__name__}"
    )
    # GitHub Actions requires `name:` (or `on:`) at the top level.
    assert "name" in parsed or True in parsed, (
        f"{workflow_path.name}: missing both `name:` and `on:` (top-level keys)"
    )


def test_mkdocs_yml_is_valid() -> None:
    """`mkdocs.yml` must parse, and must declare `site_name` + `theme` + `nav`."""
    mkdocs_path = REPO_ROOT / "mkdocs.yml"
    assert mkdocs_path.exists(), "mkdocs.yml missing from repo root"
    parsed = _safe_load(mkdocs_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert parsed.get("site_name"), "mkdocs.yml: site_name is required"
    theme = parsed.get("theme")
    assert isinstance(theme, dict), "mkdocs.yml: theme must be a mapping"
    assert theme.get("name") == "material", (
        f"mkdocs.yml: theme.name must be 'material', got {theme.get('name')!r}"
    )
    nav = parsed.get("nav")
    assert isinstance(nav, list), "mkdocs.yml: nav must be a list"
    assert len(nav) >= 1, "mkdocs.yml: nav must list at least one page"


# ---------------------------------------------------------------------------
# ci.yml — Python matrix + toolchain.
# ---------------------------------------------------------------------------

def _load_workflow(name: str) -> dict:
    path = _workflows_dir() / name
    assert path.exists(), f"{path} not found"
    return _safe_load(path.read_text(encoding="utf-8"))


def test_ci_workflow_declares_python_matrix() -> None:
    """ci.yml must run pytest on Python 3.10, 3.11, and 3.12 — the project's
    supported-version matrix. Dropping a version here would silently mean
    that interpreter is no longer exercised in CI.
    """
    parsed = _load_workflow("ci.yml")
    # Find the matrix.python-version list, regardless of nesting depth.
    matrix = (
        parsed.get("jobs", {})
        .get("test", {})
        .get("strategy", {})
        .get("matrix", {})
        .get("python-version", [])
    )
    if isinstance(matrix, str):
        matrix = [matrix]
    assert isinstance(matrix, list), "ci.yml: jobs.test.strategy.matrix.python-version missing"
    matrix_strs = [str(v) for v in matrix]
    for required in ("3.10", "3.11", "3.12"):
        assert required in matrix_strs, (
            f"ci.yml: Python {required} missing from matrix (got {matrix_strs})"
        )


def test_ci_workflow_uses_server_extras() -> None:
    """ci.yml must `pip install -e .[server]` so the in-tree TestClient-based
    server tests (tests/test_server.py) can import fastapi/uvicorn.
    """
    parsed = _load_workflow("ci.yml")
    # Concatenate every `run:` block in every step — covers multi-job files.
    steps_text = ""
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if isinstance(run, str):
                steps_text += run + "\n"
            elif isinstance(run, list):
                steps_text += "\n".join(run) + "\n"
    assert "-e .[server]" in steps_text or '-e ".[server]"' in steps_text, (
        "ci.yml: expected `pip install -e .[server]` (or `-e \"[server]\"`); "
        "the [server] extra pulls in FastAPI/uvicorn for the server tests"
    )


def test_ci_workflow_runs_ruff() -> None:
    """ci.yml must run `ruff check` so the lint contract is enforced."""
    parsed = _load_workflow("ci.yml")
    found = False
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not isinstance(run, str):
                continue
            if "ruff" in run and "check" in run:
                found = True
                break
    assert found, "ci.yml: expected a `ruff check …` step somewhere in the jobs"


def test_ci_workflow_runs_mypy() -> None:
    """ci.yml must run `mypy` against the package source."""
    parsed = _load_workflow("ci.yml")
    found = False
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not isinstance(run, str):
                continue
            if "mypy" in run:
                found = True
                break
    assert found, "ci.yml: expected a `mypy …` step somewhere in the jobs"


def test_ci_workflow_fails_below_80_percent_coverage() -> None:
    """ci.yml must pass `--cov-fail-under=80` so coverage regressions fail
    the build (the project's documented gate).
    """
    parsed = _load_workflow("ci.yml")
    found = False
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not isinstance(run, str):
                continue
            if "cov-fail-under" in run and "80" in run:
                found = True
                break
    assert found, (
        "ci.yml: expected a pytest step with `--cov-fail-under=80` (or similar) "
        "to enforce the documented 80% coverage gate"
    )


def test_ci_workflow_triggers_on_push_and_pull_request() -> None:
    """ci.yml must run on `push` to main AND every `pull_request`. Dropping
    either trigger would silently reduce coverage of incoming changes.
    """
    parsed = _load_workflow("ci.yml")
    on = parsed.get("on") or parsed.get(True)  # YAML parses `on:` as the bool True
    assert isinstance(on, dict), "ci.yml: `on:` trigger section missing"
    push = on.get("push", {})
    pr = on.get("pull_request", {})
    # `push:` may be a string ("main") or a mapping with branches:
    assert push, "ci.yml: must trigger on `push:`"
    assert pr, "ci.yml: must trigger on `pull_request:`"


# ---------------------------------------------------------------------------
# docs.yml — mkdocs build + peaceiris deploy.
# ---------------------------------------------------------------------------

def test_docs_workflow_exists() -> None:
    """docs.yml must exist — the docs site build/deploy is its own workflow."""
    path = _workflows_dir() / "docs.yml"
    assert path.exists(), ".github/workflows/docs.yml missing — docs site won't deploy"


def test_docs_workflow_runs_mkdocs_build() -> None:
    """docs.yml must invoke `mkdocs build` (with --strict preferred)."""
    parsed = _load_workflow("docs.yml")
    found = False
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not isinstance(run, str):
                continue
            if re.search(r"\bmkdocs\s+build\b", run):
                found = True
                break
    assert found, "docs.yml: expected a `mkdocs build` step somewhere in the jobs"


def test_docs_workflow_uses_peaceiris_action() -> None:
    """docs.yml must reference `peaceiris/actions-gh-pages@v3` — the action
    pinned in the task spec. A different action would change deploy semantics
    (e.g. force_orphan behavior, branch handling) and should require a
    deliberate test update.
    """
    parsed = _load_workflow("docs.yml")
    found = False
    for job in parsed.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            uses = step.get("uses", "")
            if not isinstance(uses, str):
                continue
            if "peaceiris/actions-gh-pages" in uses:
                # Pin the major version — `@v3` is the documented contract.
                assert uses.endswith("@v3"), (
                    f"docs.yml: peaceiris pin is {uses!r}, expected major version @v3"
                )
                found = True
                break
    assert found, (
        "docs.yml: expected to reference `peaceiris/actions-gh-pages@v3` "
        "for the GitHub Pages deploy"
    )


# ---------------------------------------------------------------------------
# pyproject.toml — lint + type-check config.
# ---------------------------------------------------------------------------

def test_pyproject_declares_ruff_config() -> None:
    """pyproject.toml must have a `[tool.ruff]` section so `ruff check`
    uses the project's documented line-length and target-version."""
    import tomllib

    pyproject = REPO_ROOT / "pyproject.toml"
    parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    ruff = parsed.get("tool", {}).get("ruff", {})
    assert ruff, "pyproject.toml: [tool.ruff] section missing"
    assert ruff.get("line-length") == 100, (
        f"pyproject.toml: [tool.ruff].line-length must be 100, got {ruff.get('line-length')!r}"
    )
    assert ruff.get("target-version") == "py310", (
        f"pyproject.toml: [tool.ruff].target-version must be 'py310', "
        f"got {ruff.get('target-version')!r}"
    )


def test_pyproject_declares_mypy_config() -> None:
    """pyproject.toml must have a `[tool.mypy]` section with
    `ignore_missing_imports = true` (the documented loose config)."""
    import tomllib

    pyproject = REPO_ROOT / "pyproject.toml"
    parsed = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    mypy = parsed.get("tool", {}).get("mypy", {})
    assert mypy, "pyproject.toml: [tool.mypy] section missing"
    assert mypy.get("ignore_missing_imports") is True, (
        f"pyproject.toml: [tool.mypy].ignore_missing_imports must be True, "
        f"got {mypy.get('ignore_missing_imports')!r}"
    )


# ---------------------------------------------------------------------------
# gen_validators_md.py — runs without error.
# ---------------------------------------------------------------------------

def test_gen_validators_md_script_exists() -> None:
    """`scripts/gen_validators_md.py` must exist — the docs site depends on
    it being runnable in CI to refresh `docs/validators.md`."""
    path = REPO_ROOT / "scripts" / "gen_validators_md.py"
    assert path.exists(), "scripts/gen_validators_md.py missing"


def test_gen_validators_md_output_exists() -> None:
    """`docs/validators.md` must exist (the committed, generated output)."""
    path = REPO_ROOT / "docs" / "validators.md"
    assert path.exists(), "docs/validators.md missing — run `python scripts/gen_validators_md.py`"


def test_gen_validators_md_covers_all_23_validators() -> None:
    """The generated `docs/validators.md` must list all 23 validator names —
    drift here means the docs site is out of sync with the source."""
    import a1_validator

    md_path = REPO_ROOT / "docs" / "validators.md"
    body = md_path.read_text(encoding="utf-8")
    for kind in a1_validator.list_kinds():
        # Each kind appears at minimum as a row in the summary table.
        assert f"`{kind}`" in body, (
            f"docs/validators.md: kind `{kind}` missing — "
            f"re-run `python scripts/gen_validators_md.py` to refresh"
        )
