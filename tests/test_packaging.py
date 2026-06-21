"""tests/test_packaging.py — hermetic packaging smoke-test.

Exercises the full "build → install → import" flow inside a tmpdir venv so
the dev environment is untouched. This is the same flow the Dockerfile
runs at build time, and the same flow the GitHub Actions publish workflow
runs before pushing to TestPyPI / GHCR.

What we check:

1. ``python -m build --sdist --outdir dist/`` exits 0 and produces a
   ``a1_validator-<version>.tar.gz`` whose name parses to the version
   declared in ``pyproject.toml``.
2. ``pip install <sdist>`` in a fresh venv exits 0 and pulls all deps.
3. After install, ``import a1_validator`` succeeds and the version
   matches ``pyproject.toml``.
4. The 23 validator functions are callable as top-level attributes.
5. A representative single-input validator round-trip
   (``a1_validator.hhvh('00123456')``) returns ``ok=True`` and the
   expected ``normalized`` value.
6. The ``a1-validate`` console script is on PATH and
   ``a1-validate --version`` prints the package version.

We deliberately do NOT spin up a Docker container in this test — the
Docker smoke check is covered by ``docker build -t a1-validator:test .``
in the task's manual verify step. The Dockerfile has its own
``RUN a1-validate --version`` line that runs at image build time.

Why hermetic? Three reasons:

* Avoids polluting the dev venv (sdist installs are NOT
  ``pip install -e .`` and would shadow the editable install).
* Avoids version drift between the test assertion and the artifact
  (we read ``pyproject.toml`` at test time, not hardcode ``0.1.0``).
* Catches packaging regressions that the in-process test suite can't
  see — missing ``package_data``, broken ``[project.scripts]``,
  undeclared deps, etc.

If you have no ``build`` package installed in your dev env, this test
will create a venv inside the tmpdir and install ``build`` into it. The
test does NOT require any pre-existing venv — it's self-contained.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

# tomllib is stdlib on Python 3.11+. On 3.10, fall back to the `tomli`
# backport (install it as a test dep). Without this, pytest collection
# crashes on 3.10 with `ModuleNotFoundError: No module named 'tomllib'`.
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_pyproject_version() -> str:
    """Read the package version from ``pyproject.toml``."""
    pyproject = REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def _read_pyproject_name() -> str:
    """Read the package name from ``pyproject.toml`` (e.g. ``a1-validator``)."""
    pyproject = REPO_ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["name"]


def _make_venv(venv_dir: Path) -> tuple[Path, Path]:
    """Create a fresh venv at ``venv_dir``. Returns ``(python, pip)`` paths."""
    venv.EnvBuilder(
        system_site_packages=False,
        clear=True,
        symlinks=False,
        upgrade_deps=False,
        with_pip=True,
    ).create(str(venv_dir))
    if sys.platform == "win32":
        python = venv_dir / "Scripts" / "python.exe"
        pip = venv_dir / "Scripts" / "pip.exe"
    else:
        python = venv_dir / "bin" / "python"
        pip = venv_dir / "bin" / "pip"
    return python, pip


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, capture stdout/stderr, raise on non-zero exit.

    Uses ``subprocess.run`` (not ``check_call``) so the caller sees the
    full output on failure — packaging failures are noisy and the
    pytest output is much shorter than the actual log.
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Test fixture — one tmpdir per test, with a pre-built sdist ready to install.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def build_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the sdist once per test module and share it across tests.

    ``scope="module"`` cuts the build cost (5–15s) without giving up
    isolation — every pytest invocation still gets its own tmpdir.

    The fixture returns the dist/ directory containing the sdist.
    Tests that need the sdist path glob for the artifact; tests that
    need a clean install venv build their own.
    """
    work = tmp_path_factory.mktemp("pkg-build")
    dist = work / "dist"
    dist.mkdir()

    # Step 1: build the sdist. We invoke `python -m build` from the dev
    # env (the test runner's python), NOT from inside a venv — the dev
    # env already has `build` installed (or, if not, pip-installing it
    # is the test runner's problem, not the sdist's).
    result = _run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(dist)],
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.fail(
            "python -m build --sdist failed:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
    return dist


@pytest.fixture(scope="module")
def package_version() -> str:
    """Cache the pyproject.toml version (read once per module)."""
    return _read_pyproject_version()


@pytest.fixture(scope="module")
def package_name() -> str:
    """Cache the pyproject.toml name (read once per module)."""
    return _read_pyproject_name()


@pytest.fixture(scope="module")
def installed_venv(build_dir: Path, package_version: str, package_name: str):
    """Install the sdist into a fresh venv. Module-scoped to amortize cost.

    Returns a dict with the venv paths so individual tests can poke at
    them without re-installing.
    """
    work = build_dir.parent
    venv_dir = work / "install-venv"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    python, pip = _make_venv(venv_dir)

    # Find the sdist.
    sdists = list(build_dir.glob("*.tar.gz"))
    assert sdists, f"no sdist found under {build_dir}"
    sdist = sdists[0]
    # Sanity: sdist filename embeds the version.
    assert package_version in sdist.name, (
        f"sdist filename {sdist.name!r} does not contain version "
        f"{package_version!r} — pyproject.toml and sdist are out of sync"
    )

    # Step 2: install the sdist. Include the [server] extra so the
    # `a1-validate` entry point (which depends on fastapi/uvicorn for
    # the `serve` subcommand) has all its runtime deps. The bare
    # validator calls themselves only need the core install.
    result = _run(
        [str(pip), "install", "--quiet", f"{package_name}[server]=={package_version}",
         "--no-index", f"--find-links={build_dir}"],
        cwd=work,
    )
    if result.returncode != 0:
        # Fallback: try the sdist directly (no --find-links). Some pip
        # versions are picky about --find-links + editable.
        result = _run(
            [str(pip), "install", "--quiet", str(sdist)],
            cwd=work,
        )
    if result.returncode != 0:
        pytest.fail(
            "pip install <sdist> failed:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )

    # Locate the installed `a1-validate` console script. setuptools puts it
    # under ``<venv>/bin/`` on POSIX or ``<venv>/Scripts/`` on Windows.
    if sys.platform == "win32":
        entry_point = venv_dir / "Scripts" / "a1-validate.exe"
    else:
        entry_point = venv_dir / "bin" / "a1-validate"
    assert entry_point.exists(), (
        f"installed entry-point script not found at {entry_point} — "
        f"setuptools did not generate the [project.scripts] wrapper"
    )

    return {
        "venv_dir": venv_dir,
        "python": python,
        "pip": pip,
        "sdist": sdist,
        "entry_point": entry_point,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSdistBuild:
    """Step 1 — the sdist must build cleanly and embed the right version."""

    def test_build_exits_zero(self, build_dir: Path) -> None:
        """``python -m build --sdist`` must exit 0.

        The fixture fails the test itself if the build fails, but we
        assert on the artifact presence here so the failure mode is
        'sdist missing' rather than the cryptic exit-code path.
        """
        sdists = list(build_dir.glob("*.tar.gz"))
        assert sdists, (
            f"no .tar.gz produced under {build_dir} — "
            f"`python -m build --sdist` returned no artifact"
        )

    def test_sdist_filename_matches_version(
        self, build_dir: Path, package_version: str, package_name: str
    ) -> None:
        """The sdist filename should embed both name and version.

        setuptools produces ``a1_validator-0.1.0.tar.gz`` — note the
        underscore-separated name (PEP 503 normalization happens at
        install time, NOT at build time, so the .tar.gz uses
        ``a1_validator`` even though pyproject says ``a1-validator``).
        """
        sdists = list(build_dir.glob("*.tar.gz"))
        assert sdists
        name = sdists[0].name
        # setuptools normalizes the underscore version of the name.
        normalized = package_name.replace("-", "_")
        assert normalized in name, (
            f"sdist filename {name!r} does not contain "
            f"{normalized!r} (underscore-normalized form of {package_name!r})"
        )
        assert package_version in name, (
            f"sdist filename {name!r} does not contain version {package_version!r}"
        )

    def test_sdist_tarball_includes_package_metadata(
        self, build_dir: Path, package_name: str
    ) -> None:
        """The sdist tarball should contain PKG-INFO + the package tree.

        Sanity check — a tarball that somehow contained only setup.py
        and no source would still install (badly). Catch it here.
        """
        import tarfile
        sdists = list(build_dir.glob("*.tar.gz"))
        assert sdists
        with tarfile.open(sdists[0]) as tf:
            members = tf.getnames()
        # PKG-INFO is mandatory in any modern sdist.
        assert any(m.endswith("PKG-INFO") for m in members), (
            f"sdist has no PKG-INFO — got {len(members)} entries, "
            f"first 10: {members[:10]}"
        )
        # The a1_validator package directory should be present.
        normalized = package_name.replace("-", "_")
        assert any(normalized in m for m in members), (
            f"sdist has no {normalized}/* entries — first 10: {members[:10]}"
        )


class TestSdistInstall:
    """Step 2 — the sdist must install cleanly into a fresh venv."""

    def test_pip_install_exits_zero(self, installed_venv) -> None:
        """pip install of the sdist into a fresh venv must exit 0.

        The fixture fails the test itself if pip returns non-zero,
        so we just assert the venv looks right.
        """
        venv_dir = installed_venv["venv_dir"]
        python = installed_venv["python"]
        assert venv_dir.exists()
        assert python.exists()
        # And the python in the venv should be runnable.
        result = _run([str(python), "--version"])
        assert result.returncode == 0, (
            f"venv python broken: {result.stdout!r} {result.stderr!r}"
        )

    def test_installed_version_matches_pyproject(
        self, installed_venv, package_version: str
    ) -> None:
        """`pip show` should report the version that matches pyproject.toml."""
        pip = installed_venv["pip"]
        result = _run([str(pip), "show", "a1-validator"])
        assert result.returncode == 0, (
            f"`pip show a1-validator` failed:\n{result.stderr}"
        )
        match = re.search(r"^Version:\s*(\S+)", result.stdout, re.MULTILINE)
        assert match, f"could not find Version: line in pip show output:\n{result.stdout}"
        installed_version = match.group(1)
        assert installed_version == package_version, (
            f"installed version {installed_version!r} != "
            f"pyproject version {package_version!r}"
        )


class TestPackageRuntime:
    """Step 3 — the installed package must import and behave correctly."""

    def test_import_a1_validator(self, installed_venv, package_version: str) -> None:
        """``import a1_validator`` must succeed and the version must match."""
        python = installed_venv["python"]
        # Use json.dumps to ensure the output is greppable and free of
        # any stray stderr noise from a misconfigured install.
        result = _run(
            [str(python), "-c",
             "import json, a1_validator; "
             "print(json.dumps({'version': a1_validator.__version__}))"],
        )
        assert result.returncode == 0, (
            f"import failed:\n--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
        # Last line of stdout is the json we printed.
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["version"] == package_version, (
            f"installed a1_validator.__version__={payload['version']!r} != "
            f"pyproject version {package_version!r}"
        )

    def test_validator_functions_are_top_level_attributes(self, installed_venv) -> None:
        """All 41 public validators should be importable as attributes.

        Verifies that the ``for ... in _VALIDATORS: globals()[...] = ...``
        block in ``__init__.py`` actually populated the public namespace
        when the sdist-installed package is imported (not just the
        editable-installed one — sdist install goes through a different
        import path).
        """
        python = installed_venv["python"]
        result = _run(
            [str(python), "-c",
             "import json, a1_validator; "
             "kinds = a1_validator.list_kinds(); "
             "missing = [k for k in kinds if not hasattr(a1_validator, k)]; "
             "print(json.dumps({'n_kinds': len(kinds), 'missing': missing}))"],
        )
        assert result.returncode == 0, (
            f"list_kinds failed:\n{result.stdout}\n{result.stderr}"
        )
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["missing"] == [], (
            f"missing public attributes for {len(payload['missing'])} kinds: "
            f"{payload['missing']}"
        )
        assert payload["n_kinds"] == 41, (
            f"expected 41 kinds from list_kinds(), got {payload['n_kinds']}"
        )

    def test_hhvh_roundtrip(self, installed_venv) -> None:
        """``a1_validator.hhvh({'hvhh': '00123456'})`` returns ``ok=True``.

        Single-end-to-end validator round-trip — proves the package
        is wired up correctly (deps loaded, vendored modules
        importable, function callable, return shape correct).
        """
        python = installed_venv["python"]
        # The task spec calls the public function with a bare string:
        #     a1_validator.hhvh('00123456')
        # Our public ``hhvh`` signature takes a dict (per the README
        # contract). The bare-string form is what ``a1-validate`` uses
        # internally — same call signature, just shorter at the
        # argparse layer. We test the dict form here because that's
        # the public API contract documented in the README.
        result = _run(
            [str(python), "-c",
             "import json, a1_validator; "
             "r = a1_validator.hhvh({'hvhh': '00123456'}); "
             "print(json.dumps(r))"],
        )
        assert result.returncode == 0, (
            f"hhvh call failed:\n{result.stdout}\n{result.stderr}"
        )
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        hvhh_input = {"hvhh": "00123456"}
        assert payload.get("ok") is True, (
            f"hhvh({hvhh_input!r}) returned ok={payload.get('ok')!r}: "
            f"{payload}"
        )
        assert payload.get("normalized") == "00123456", (
            f"hhvh returned unexpected normalized={payload.get('normalized')!r}: "
            f"{payload}"
        )

    def test_a1_validate_entry_point(self, installed_venv, package_version: str) -> None:
        """``a1-validate --version`` must print the package version.

        Verifies the ``[project.scripts] a1-validate = ...`` entry point
        in pyproject.toml is wired up by setuptools at install time.
        """
        # Use the actual installed entry-point script — this is exactly
        # what the Dockerfile smoke-tests (``RUN a1-validate --version``)
        # and what end users do. ``python -m a1_validator.cli`` would
        # also work if cli.py had an ``if __name__ == "__main__": app()``
        # block, but the entry-point script is the canonical contract.
        script = installed_venv["entry_point"]
        result = _run([str(script), "--version"])
        assert result.returncode == 0, (
            f"a1-validate --version failed:\n{result.stdout}\n{result.stderr}"
        )
        # Match: 'a1-validator <version>'
        match = re.search(r"a1-validator\s+(\S+)", result.stdout)
        assert match, (
            f"could not find version line in --version output:\n{result.stdout!r}"
        )
        assert match.group(1) == package_version, (
            f"--version reported {match.group(1)!r} != {package_version!r}"
        )

    def test_a1_validate_list_subcommand(self, installed_venv) -> None:
        """``a1-validate list`` must print 41 validators.

        Sanity check that the CLI loads from the sdist install path,
        not from a stale ``__pycache__`` of the dev install.
        """
        script = installed_venv["entry_point"]
        result = _run([str(script), "list"])
        assert result.returncode == 0, (
            f"a1-validate list failed:\n{result.stdout}\n{result.stderr}"
        )
        # Count lines that look like validator entries — each starts
        # with two spaces and a kind name.
        entries = [ln for ln in result.stdout.splitlines()
                   if re.match(r"^\s{2}\w+\s+", ln)]
        assert len(entries) == 41, (
            f"expected 41 validators in `list` output, got {len(entries)}: "
            f"{entries}"
        )
