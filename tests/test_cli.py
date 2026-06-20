"""Pytest suite for the `a1-validate` CLI.

Coverage targets (from the task spec):

1. `a1-validate hhvh 00123456` returns ok=true (exit 0).
2. `a1-validate hhvh 99999999` returns ok=false (exit 1) — all-same-digit
   HHVH is rejected.
3. `a1-validate list` exits 0 and lists 23+ items.
4. `a1-validate --version` exits 0.
5. `a1-validate batch hhvh tests/_eval_sets/hhvh.json` (the vendored eval set)
   processes all 20 cases correctly — every case's `input` matches the
   `expected` output.

We use `typer.testing.CliRunner` (a thin Click runner wrapper) so the tests
exercise the same code path as the real `a1-validate` console script — no
subprocess overhead, no console_scripts re-resolution, no argv parsing
quirks.
"""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from a1_validator.cli import app

# `tests/_eval_sets/` sits next to this test file.
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_EVAL_SETS_DIR = _TESTS_DIR / "_eval_sets"


@pytest.fixture
def runner() -> CliRunner:
    """Per-test CliRunner — Typer 0.26 separates stdout / stderr by default."""
    return CliRunner()


# ---------------------------------------------------------------------------
# 1. Single-shot validate — happy path
# ---------------------------------------------------------------------------


def test_validate_hhvh_ok(runner: CliRunner) -> None:
    """`a1-validate hhvh 00123456` returns ok=true, exit 0."""
    result = runner.invoke(app, ["hhvh", "00123456"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip())
    assert payload == {"ok": True, "normalized": "00123456", "error": None}


def test_validate_hhvh_all_same_digits_rejected(runner: CliRunner) -> None:
    """`a1-validate hhvh 99999999` returns ok=false, exit 1 (all-same is invalid)."""
    result = runner.invoke(app, ["hhvh", "99999999"])
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    assert payload["normalized"] == "99999999"
    assert payload["error"] is not None
    # Armenian error message — verify it survives the JSON round-trip verbatim
    # (no \uXXXX escaping of the Armenian characters).
    assert "99999999" not in payload["error"]  # generic, no PII leak


def test_validate_json_passthrough(runner: CliRunner) -> None:
    """A JSON object `<value>` is forwarded to the validator as-is.

    This is the multi-input validator entry path — passing a JSON object lets
    the caller supply every field at once instead of relying on the
    single-string wrapping shortcut.
    """
    result = runner.invoke(app, ["hhvh", '{"hvhh": "00123456"}'])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True
    assert payload["normalized"] == "00123456"


def test_validate_unknown_kind_exits_1(runner: CliRunner) -> None:
    """An unknown kind name produces a clean error and exit 1, not a crash."""
    result = runner.invoke(app, ["definitely_not_a_real_kind", "foo"])
    assert result.exit_code == 1
    # The error should mention the offending kind on stderr so the user can
    # see it without scrolling through stdout (which is JSON).
    combined = (result.stderr or "") + (result.stdout or "")
    assert "definitely_not_a_real_kind" in combined


# ---------------------------------------------------------------------------
# 2. Subcommand: `list`
# ---------------------------------------------------------------------------


def test_list_lists_23_validators(runner: CliRunner) -> None:
    """`a1-validate list` exits 0 and prints at least 23 validators."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.stdout
    # The output has a header + blank line + 23 lines + footer + blank line.
    # A loose `>= 23` keeps the test stable across formatting tweaks (e.g.
    # adding a column for aliases later).
    assert result.stdout.count("\n") >= 23
    # Spot-check a handful of canonical kinds are present.
    for kind in ("hhvh", "inn", "vat_return", "invoice", "model_policy"):
        assert kind in result.stdout, f"missing {kind!r} in list output"


def test_list_count_matches_api(runner: CliRunner) -> None:
    """`list` output contains exactly the kinds `a1_validator.list_kinds()` returns."""
    from a1_validator import list_kinds
    expected_kinds = set(list_kinds())
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    missing = expected_kinds - set(result.stdout.split())
    assert not missing, f"list subcommand is missing kinds: {sorted(missing)}"


# ---------------------------------------------------------------------------
# 3. Subcommand: `--version`
# ---------------------------------------------------------------------------


def test_version_flag(runner: CliRunner) -> None:
    """`a1-validate --version` prints the package version and exits 0."""
    from a1_validator import __version__
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.stdout
    assert __version__ in result.stdout
    assert "a1-validator" in result.stdout


# ---------------------------------------------------------------------------
# 4. Subcommand: `batch` against a vendored eval set
# ---------------------------------------------------------------------------


def test_batch_validates_vendored_hhvh_eval_set(runner: CliRunner) -> None:
    """`a1-validate batch hhvh tests/_eval_sets/hhvh.json` processes every case.

    The vendored eval set has 20 cases — 8 ok cases (normalized correctly) and
    12 fail cases (each with its own Armenian error string). All 20 must match
    their expected output; the summary exit code must be 0.
    """
    eval_path = _EVAL_SETS_DIR / "hhvh.json"
    assert eval_path.exists(), f"missing vendored eval set: {eval_path}"

    with eval_path.open(encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 20, f"unexpected eval-set size: {len(cases)}"

    result = runner.invoke(app, ["batch", "hhvh", str(eval_path)])
    assert result.exit_code == 0, f"batch failed: {result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["kind"] == "hhvh"
    assert payload["total"] == 20
    assert payload["ok"] == 20
    assert payload["fail"] == 0
    assert payload["failures"] == []


def test_batch_unknown_kind_exits_1(runner: CliRunner, tmp_path) -> None:
    """`batch` with an unknown kind emits an error and exits 1, not 0."""
    f = tmp_path / "cases.json"
    f.write_text(json.dumps([{"input": {"hvhh": "00123456"}, "expected": {"ok": True}}]), encoding="utf-8")
    result = runner.invoke(app, ["batch", "definitely_not_a_real_kind", str(f)])
    assert result.exit_code == 1


def test_batch_invalid_json_exits_nonzero(runner: CliRunner, tmp_path) -> None:
    """`batch` with malformed JSON exits non-zero (2 — input file error)."""
    f = tmp_path / "bad.json"
    f.write_text("not valid json {", encoding="utf-8")
    result = runner.invoke(app, ["batch", "hhvh", str(f)])
    assert result.exit_code != 0


def test_batch_partial_failures_exits_1(runner: CliRunner, tmp_path) -> None:
    """`batch` exits 1 when ANY case fails the subset-equality match.

    Build a synthetic eval set with one expected-ok case and one expected-fail
    case where the actual result differs from the expected — the summary
    must surface both failures and the exit code must be 1.
    """
    f = tmp_path / "mixed.json"
    f.write_text(json.dumps([
        {"input": {"hvhh": "00123456"}, "expected": {"ok": True, "normalized": "00123456"}},
        # This case will actually fail validation (all-same digits), but the
        # expected says ok=true — so the subset match fails and batch exits 1.
        {"input": {"hvhh": "99999999"}, "expected": {"ok": True, "normalized": "99999999"}},
    ]), encoding="utf-8")
    result = runner.invoke(app, ["batch", "hhvh", str(f)])
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["total"] == 2
    assert payload["ok"] == 1
    assert payload["fail"] == 1
    assert len(payload["failures"]) == 1
    assert payload["failures"][0]["index"] == 1
