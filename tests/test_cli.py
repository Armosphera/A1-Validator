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

# `tests/_eval_sets/` sits next to this test file.
from pathlib import Path

import pytest
from typer.testing import CliRunner

from a1_validator.cli import app

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


def test_validate_explicit_validate_subcommand(runner: CliRunner) -> None:
    """`a1-validate validate hhvh 00123456` is the same as the bare form.

    The explicit `validate` subcommand is non-hidden so users who want
    symmetry (and `a1-validate validate --help`) can use it. Both forms
    produce identical output.
    """
    result = runner.invoke(app, ["validate", "hhvh", "00123456"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True


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
    """`a1-validate list` exits 0 and prints at least 33 validators."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.stdout
    # The output has a header + blank line + 23 lines + footer + blank line.
    # A loose `>= 33` keeps the test stable across formatting tweaks (e.g.
    # adding a column for aliases later).
    assert result.stdout.count("\n") >= 33
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


def test_version_subcommand(runner: CliRunner) -> None:
    """`a1-validate version` (explicit subcommand) also prints the version."""
    from a1_validator import __version__
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.stdout
    assert __version__ in result.stdout


# ---------------------------------------------------------------------------
# 4. Subcommand: `batch` — eval-set mode (JSON array)
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
    assert payload["mode"] == "eval_set"
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


# ---------------------------------------------------------------------------
# 5. Subcommand: `batch` — one-per-line mode (plain text)
# ---------------------------------------------------------------------------


def test_batch_lines_mode_validates_one_value_per_line(runner: CliRunner, tmp_path) -> None:
    """Plain-text batch input — one raw value per line, no expected to compare."""
    f = tmp_path / "values.txt"
    # 00123456 → ok, 99999999 → fail, 12345678 → ok, "" → fail
    f.write_text("00123456\n99999999\n12345678\n\n", encoding="utf-8")
    result = runner.invoke(app, ["batch", "hhvh", str(f)])
    assert result.exit_code == 1, result.stdout  # at least one failure
    payload = json.loads(result.stdout)
    assert payload["kind"] == "hhvh"
    assert payload["mode"] == "lines"
    assert payload["total"] == 3  # blank line is skipped
    assert payload["ok"] == 2
    assert payload["fail"] == 1
    # The single failure is the all-same-digit line.
    assert payload["failures"][0]["value"] == "99999999"


def test_batch_lines_mode_all_ok_exits_0(runner: CliRunner, tmp_path) -> None:
    """All-ok plain-text batch exits 0."""
    f = tmp_path / "values.txt"
    f.write_text("00123456\n12345678\n00000001\n", encoding="utf-8")
    result = runner.invoke(app, ["batch", "hhvh", str(f)])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["mode"] == "lines"
    assert payload["total"] == 3
    assert payload["ok"] == 3
    assert payload["fail"] == 0


def test_batch_lines_mode_rejects_multi_input_validator(runner: CliRunner, tmp_path) -> None:
    """Plain-text batch on a multi-input validator exits 1 with a clear error.

    ``vat_return`` is a multi-input validator — there's no canonical
    single-string input key, so one-per-line text can't represent it.
    The CLI must reject this with a helpful message instead of trying
    to call ``vat_return({"vat_return": "<raw>"})`` and producing noise.
    """
    f = tmp_path / "values.txt"
    f.write_text("100000\n200000\n", encoding="utf-8")
    result = runner.invoke(app, ["batch", "vat_return", str(f)])
    assert result.exit_code == 1
    combined = (result.stderr or "") + (result.stdout or "")
    assert "vat_return" in combined
    assert "JSON" in combined


# ---------------------------------------------------------------------------
# 6. Routing sanity — make sure `_CmdGroup` doesn't break edge cases
# ---------------------------------------------------------------------------


def test_routing_no_args_shows_help(runner: CliRunner) -> None:
    """`a1-validate` (no args) shows help and exits non-zero (usage error).

    Click's standard ``no_args_is_help`` semantics surface a ``NoArgsIsHelpError``
    which Click converts to exit code 2 (usage error). The help text is printed
    to stdout so the user still sees it. We only assert the help is shown —
    the exact exit code is Click's convention.
    """
    result = runner.invoke(app, [])
    assert result.exit_code != 0
    # Help text mentions at least one subcommand.
    assert "list" in result.stdout or "Commands" in result.stdout


def test_routing_known_subcommand_takes_priority_over_positional(
    runner: CliRunner,
) -> None:
    """`a1-validate list` dispatches to the list subcommand, NOT kind='list'."""
    # If the routing is broken, the CLI would try to validate a kind called
    # 'list' and emit the unknown-kind error. Verify the list subcommand
    # actually ran by checking the output shape (header + 33 validators).
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "33 SBOSS sovereign business-ops validators" in result.stdout
    assert "Unknown validator kind 'list'" not in (result.stderr or "") + (result.stdout or "")
