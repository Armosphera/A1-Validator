"""a1-validate CLI — Typer-based command-line interface for the 23 SBOSS validators.

Usage:
    a1-validate <kind> <value>          Validate a single value, print JSON result.
    a1-validate list                    List all 23 validators with one-liners.
    a1-validate batch <kind> <file>     Validate every case in a vendored eval set.
    a1-validate --version               Print a1_validator.__version__.

Input handling for `a1-validate <kind> <value>`:
- If <value> parses as a JSON object, it is forwarded to the validator as-is
  (this is the natural shape for multi-input validators like `vat_return` and
  `chat_client`).
- Otherwise <value> is treated as a single string and wrapped under the
  validator's canonical input key (e.g. `a1-validate hhvh 00123456` becomes
  `{"hvhh": "00123456"}` for the hhvh validator).

The mapping from kind → single-string input key is kept in
``_SINGLE_INPUT_KEY`` — only kinds whose vendored `validate(input_data)` reads
exactly one string field appear here. Multi-input validators (model_policy,
vat_return, vat_return_form, chat_client, ru_einvoice, payroll_ru, vat_ru,
settings_store, model_catalog, supplemental_sources, open_notebook,
product_research) require a JSON object and raise a clear error otherwise.

Exit codes:
- 0 — validation succeeded (ok=True) OR a list/version/informational command.
- 1 — validation failed (ok=False) OR an unknown kind was supplied.
- 2 — internal error (unhandled exception in the vendored validator).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import click
import typer
import typer.core

import a1_validator


# ---------------------------------------------------------------------------
# Custom TyperGroup — prioritize subcommand names over positional args.
#
# Stock Click parses positional args greedily before checking for subcommand
# names. When the main app declares `(kind, value)` positionals AND has
# subcommands like `list` / `batch`, calling `a1-validate list` binds `list`
# to the `kind` positional instead of dispatching to the `list` subcommand.
#
# We fix this by subclassing `typer.core.TyperGroup` and pre-routing the
# first non-option arg: if it matches a registered subcommand name, we let
# Typer dispatch normally; otherwise we prepend a hidden `_validate_default`
# sentinel so the two positionals bind to that subcommand's params.
# ---------------------------------------------------------------------------


class _CmdGroup(typer.core.TyperGroup):
    """TyperGroup that prioritizes subcommand names over the parent's
    positional args.

    Falls back to `_validate_default <kind> <value>` for any non-option first
    arg, so the user-facing `a1-validate <kind> <value>` form keeps working
    while `a1-validate list` and `a1-validate batch ...` dispatch to their
    dedicated subcommands.
    """

    _SENTINEL = "_validate_default"

    def parse_args(  # type: ignore[override]
        self,
        ctx: click.Context,
        args: list[str],
    ) -> list[str]:
        # Find the first non-option arg — that's the candidate subcommand
        # or kind name.
        positional = [a for a in args if not a.startswith("-")]
        first = positional[0] if positional else None
        if first is not None and first in self.commands:
            # Subcommand dispatch — let Typer do its normal thing.
            return super().parse_args(ctx, args)
        if not first:
            # No positional args — let Typer process options / emit help.
            return super().parse_args(ctx, args)
        # Default: route to the hidden `_validate_default` subcommand so the
        # two positional `(kind, value)` params bind to it.
        return super().parse_args(ctx, [self._SENTINEL, *args])


# ---------------------------------------------------------------------------
# Single-string input-key mapping.
#
# For kinds whose vendored `validate(input_data)` reads exactly one scalar field
# out of the input dict, this table lets `a1-validate <kind> <value>` accept a
# plain string from the shell and forward it as the right key. Multi-input
# validators are NOT in this table — they require a JSON object.
# ---------------------------------------------------------------------------

_SINGLE_INPUT_KEY: dict[str, str] = {
    "hhvh":                 "hvhh",
    "inn":                  "id",
    "payroll_am":           "gross",
    "chart_of_accounts_am": "code",
    "phone_am":             "phone",
    "regions_am":           "query",
    "einvoice_am":          "invoice",
    "phone_ru":             "phone",
    "chart_of_accounts_ru": "code",
    "regions_ru":           "query",
    "invoice":              "document",
}


# One-liner description per validator — kept in sync with the README's table.
# Used by the `list` subcommand.
_DESCRIPTIONS: dict[str, str] = {
    "hhvh":                 "Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ)",
    "inn":                  "Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (ru-identifiers)",
    "model_policy":         "AI model-policy resolver (module → model)",
    "vat_return":           "Armenian VAT return compute (sales/purchases → owed)",
    "payroll_am":           "Armenian payroll compute (gross → taxes/net)",
    "chart_of_accounts_am": "Armenian chart-of-accounts lookup + validate (623 accounts)",
    "vat_return_form":      "Armenian VAT-return form validation (line codes + amounts)",
    "phone_am":             "Armenian phone NSN/E.164/format",
    "regions_am":           "Armenian regions lookup (name/en/code → center)",
    "einvoice_am":          "Armenian e-invoice structural validation",
    "chat_client":          "OpenRouter chat client (mock-able HTTP transport)",
    "phone_ru":             "Russian phone NSN/E.164/format",
    "ru_einvoice":          "Russian e-invoice validate + XML build",
    "payroll_ru":           "Russian payroll (NDFL, insurance, monthly ops)",
    "regions_ru":           "Russian regions lookup (83 entries)",
    "chart_of_accounts_ru": "Russian chart-of-accounts lookup (73 accounts, 9 sections)",
    "vat_ru":               "Russian VAT rate helpers + valid-rate check",
    "settings_store":       "Local JSON settings store (read/write/list/delete)",
    "model_catalog":        "OpenRouter model catalog fetch + normalize",
    "supplemental_sources": "Supplemental research sources normalizer",
    "open_notebook":        "Notebook search/enable/normalize ops",
    "product_research":     "Product-research config + program render + decide",
    "invoice":              "Invoice field extractor (regex/mock, deterministic)",
}


# ---------------------------------------------------------------------------
# Input-shape resolution.
# ---------------------------------------------------------------------------


def _coerce_value(kind: str, raw: str) -> dict[str, Any]:
    """Turn a raw CLI string into the validator's expected input dict.

    Priority:
    1. If `raw` parses as a JSON object, return it as-is.
    2. If `kind` has a single-string input key, wrap `raw` under that key.
    3. Otherwise raise a Typer usage error pointing the user at JSON.
    """
    stripped = raw.strip()
    # 1. JSON object passthrough — handles all multi-input validators.
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"value starts with '{{' but is not valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise typer.BadParameter(
                "value is JSON but not a JSON object — the CLI expects either "
                "a JSON object or a plain string for single-input validators"
            )
        return parsed
    # 2. Plain string → wrap under the kind's canonical key.
    if kind in _SINGLE_INPUT_KEY:
        return {_SINGLE_INPUT_KEY[kind]: raw}
    # 3. Multi-input validator + non-JSON input → usage error.
    raise typer.BadParameter(
        f"validator {kind!r} requires a JSON object input (multiple fields). "
        f"Pass it inline, e.g. a1-validate {kind} '{{...}}'"
    )


# ---------------------------------------------------------------------------
# Subset-equality helper — mirrors `tests/test_validators.py::_matches` for
# the batch subcommand's pass/fail accounting.
# ---------------------------------------------------------------------------


def _subset_matches(actual: Any, expected: Any) -> bool:
    """True iff every key in ``expected`` matches a key in ``actual`` (subset)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if isinstance(k, str) and "." in k:
                cur = actual
                for part in k.split("."):
                    if isinstance(cur, dict) and part in cur:
                        cur = cur[part]
                    else:
                        return False
                if not _subset_matches(cur, v):
                    return False
            else:
                if k not in actual or not _subset_matches(actual[k], v):
                    return False
        return True
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)):
            return False
        return actual == expected  # exact float equality is fine for the CLI
    return actual == expected


# ---------------------------------------------------------------------------
# Typer app.
# ---------------------------------------------------------------------------


app = typer.Typer(
    name="a1-validate",
    add_completion=False,
    no_args_is_help=True,
    cls=_CmdGroup,
    help=(
        "Validate Armenian / Russian IDs, chart-of-accounts codes, e-invoice "
        "shapes, payroll, and more — 23 SBOSS sovereign business-ops validators "
        "exposed as a single CLI. Run `a1-validate list` to see all kinds."
    ),
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"a1-validator {a1_validator.__version__}")
        raise typer.Exit()


@app.callback()
def _app_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print a1-validator version and exit.",
    ),
) -> None:
    """Root callback — only handles `--version`. Subcommands handle everything else.

    The actual `a1-validate <kind> <value>` dispatch lives in the hidden
    `_validate_default` subcommand below; ``_CmdGroup.parse_args`` routes the
    bare two-positional form to it.
    """
    pass


def _run_validate(kind: str, value: str) -> None:
    """Single-shot validate: resolve kind, coerce value, run validator, print JSON."""
    try:
        validator = a1_validator.get_validator(kind)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        payload = _coerce_value(kind, value)
    except typer.BadParameter as exc:
        typer.echo(f"error: {exc.message if hasattr(exc, 'message') else exc}", err=True)
        raise typer.Exit(code=1)

    try:
        result = validator(payload)
    except Exception as exc:  # pragma: no cover — defensive net
        typer.echo(f"error: validator {kind!r} raised {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=2)

    typer.echo(json.dumps(result, ensure_ascii=False))
    if isinstance(result, dict) and result.get("ok") is False:
        raise typer.Exit(code=1)


@app.command(name="_validate_default", hidden=True)
def _validate_default_cmd(
    kind: str = typer.Argument(..., help="Validator name (e.g. `hhvh`, `inn`)."),
    value: Optional[str] = typer.Argument(
        None,
        help="Raw value or JSON object to validate. Optional so we can raise a friendly "
             "error instead of Click's stock `Missing argument 'VALUE'` (which leaks the "
             "internal sentinel command name).",
    ),
) -> None:
    """Hidden subcommand — bound to the bare `a1-validate <kind> <value>` form.

    ``_CmdGroup.parse_args`` routes any non-subcommand invocation here, so the
    user-facing `a1-validate hhvh 00123456` syntax maps cleanly to this body.
    """
    if value is None:
        typer.echo(
            f"error: missing <value> for validator {kind!r}. "
            f"Usage: a1-validate {kind} <value>",
            err=True,
        )
        raise typer.Exit(code=1)
    _run_validate(kind, value)


@app.command(name="list")
def list_cmd() -> None:
    """List all 23 validators with a one-line description each."""
    typer.echo(f"a1-validator {a1_validator.__version__} — 23 SBOSS validators:")
    typer.echo("")
    kinds = a1_validator.list_kinds()
    name_w = max(len(k) for k in kinds)
    for kind in kinds:
        desc = _DESCRIPTIONS.get(kind, "(no description)")
        typer.echo(f"  {kind.ljust(name_w)}  {desc}")
    typer.echo("")
    typer.echo(f"{len(kinds)} validators. Use `a1-validate <kind> <value>` to invoke one.")


@app.command()
def batch(
    kind: str = typer.Argument(..., help="Validator name (e.g. `hhvh`, `inn`)."),
    file: Path = typer.Argument(
        ...,
        help="Path to a vendored eval-set JSON file — array of {input, expected} cases.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Validate every case in a vendored eval set and print a summary.

    The file must be a JSON array of ``{input, expected}`` objects (the shape
    used by `tests/_eval_sets/<name>.json`). Each case's ``input`` is fed to
    ``a1_validator.<kind>(input)`` and the result is compared against
    ``expected`` under the same subset-equality contract as the pytest suite.

    Exit code is 0 if every case matches, 1 otherwise. The summary prints the
    total / ok / fail counts and lists every failing case with its input and
    the actual result.
    """
    try:
        validator = a1_validator.get_validator(kind)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    try:
        cases = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"error: {file} is not valid JSON: {exc}", err=True)
        raise typer.Exit(code=2)

    if not isinstance(cases, list):
        typer.echo(
            f"error: {file} must contain a JSON array of {{input, expected}} cases",
            err=True,
        )
        raise typer.Exit(code=2)

    total = len(cases)
    ok_count = 0
    failures: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict) or "input" not in case:
            failures.append({
                "index": idx,
                "error": "case is not a dict with an 'input' field",
            })
            continue
        actual = validator(case["input"])
        expected = case.get("expected", {})
        if _subset_matches(actual, expected):
            ok_count += 1
        else:
            failures.append({
                "index": idx,
                "input": case["input"],
                "actual": actual,
                "expected": expected,
            })

    fail_count = total - ok_count
    typer.echo(json.dumps({
        "kind": kind,
        "file": str(file),
        "total": total,
        "ok": ok_count,
        "fail": fail_count,
        "failures": failures,
    }, ensure_ascii=False, indent=2))

    if fail_count > 0:
        raise typer.Exit(code=1)


__all__ = ["app"]
