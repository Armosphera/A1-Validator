"""a1-validate CLI — Typer-based command-line interface for the 23 SBOSS validators.

This module exposes a single Typer ``app`` object that is registered as the
``a1-validate`` console script in ``pyproject.toml``. It is the canonical CLI
for the package — when the orchestrator merges this branch with the
``wip/http-service`` branch (which also owns ``src/a1_validator/cli.py``),
this file is the superset: keeping it preserves every subcommand defined
by either task.

Subcommands
-----------

* ``a1-validate <kind> <value>`` — default form. Validate a single value and
  print the result as JSON to stdout. Exit 0 if ``ok=true``, exit 1 if
  ``ok=false`` (or the kind is unknown).
* ``a1-validate list`` — list all 23 validators with a one-line description.
* ``a1-validate batch <kind> <file>`` — validate every case in a file. The
  file may be either (a) one raw value per line, plain text — for ad-hoc
  bulk validation — or (b) a JSON array of ``{input, expected}`` objects,
  the vendored eval-set shape. Exit 0 if every case matches expected,
  exit 1 if any case fails.
* ``a1-validate serve [--host 0.0.0.0] [--port 8000] [--reload]`` — start
  the FastAPI HTTP service defined in ``a1_validator.server``. Lazy-imports
  ``uvicorn`` so this command is the only one that pays its import cost.
  Owned by the ``wip/http-service`` task; included here so this file is a
  superset of both branches and the orchestrator's merge can drop
  http-service's ``cli.py`` in favour of ours without losing any subcommand.
* ``a1-validate --version`` / ``a1-validate version`` — print
  ``a1_validator.__version__``.

Input handling for ``<kind> <value>``
-------------------------------------

* If ``<value>`` parses as a JSON object, it is forwarded to the validator
  as-is (this is the natural shape for multi-input validators like
  ``vat_return`` and ``chat_client``).
* Otherwise ``<value>`` is treated as a single string and wrapped under
  the validator's canonical input key (e.g. ``a1-validate hhvh 00123456``
  becomes ``{"hvhh": "00123456"}`` for the hhvh validator).

The mapping from kind → single-string input key is kept in
``_SINGLE_INPUT_KEY`` — only kinds whose vendored ``validate(input_data)``
reads exactly one string field appear here. Multi-input validators
require a JSON object and raise a clear error otherwise.

Default-form routing
--------------------

The bare ``a1-validate <kind> <value>`` form needs to coexist with the
named subcommands (``list``, ``batch``, ``serve``, ``version``). Stock
Click/Typer binds the first positional arg to a callback-level ``kind``
parameter before checking for subcommand names, so without help
``a1-validate list`` would treat ``list`` as a validator name. We fix
this with the small ``_CmdGroup`` subclass below: it pre-inspects the
raw args and routes the first non-option arg to the matching subcommand
when one exists, otherwise prepends a hidden ``__validate_default``
sentinel so the two positionals bind to a dedicated subcommand.

Exit codes
----------

* ``0`` — validation succeeded (``ok=true``) OR a list/version/informational
  command completed cleanly.
* ``1`` — validation failed (``ok=false``), the kind is unknown, or the
  user gave bad input (malformed JSON, missing value, etc.).
* ``2`` — internal error (the vendored validator raised an unexpected
  exception, the eval-set file is unreadable, etc.).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import typer
import typer.core

import a1_validator

# ---------------------------------------------------------------------------
# Default-form routing — _CmdGroup.
#
# This subclass exists for ONE reason: stock Click binds positional args
# to the parent callback's params before checking for subcommand names,
# so without this override `a1-validate list` would set `kind="list"`
# and never dispatch to the `list` subcommand. We inspect the raw args
# once at parse time and prepend a hidden `__validate_default` sentinel
# when the first arg doesn't match any registered subcommand.
# ---------------------------------------------------------------------------


class _CmdGroup(typer.core.TyperGroup):
    """Typer group that prioritizes subcommand names over the parent's
    positional args.

    - If the first non-option arg matches a registered subcommand name
      (e.g. ``list``, ``batch``, ``serve``, ``version``), dispatch normally.
    - If the first non-option arg is something else (e.g. ``hhvh``,
      ``inn``), prepend a hidden ``__validate_default`` sentinel so the
      two positionals bind to that subcommand's params.
    - If there are no positional args at all, fall through to Typer's
      default behavior (show help, since ``no_args_is_help=True``).
    """

    _SENTINEL = "__validate_default"

    def parse_args(  # type: ignore[override]
        self,
        ctx: click.Context,
        args: list[str],
    ) -> list[str]:
        positional = [a for a in args if not a.startswith("-")]
        first = positional[0] if positional else None
        if first is not None and first in self.commands:
            # Subcommand dispatch — let Typer do its normal thing.
            return super().parse_args(ctx, args)  # type: ignore[arg-type]
        if not first:
            # No positional args — let Typer process options / emit help.
            return super().parse_args(ctx, args)  # type: ignore[arg-type]
        # Default: route to the hidden `__validate_default` subcommand.
        return super().parse_args(ctx, [self._SENTINEL, *args])  # type: ignore[arg-type]



# ---------------------------------------------------------------------------
# Single-string input-key mapping.
#
# For kinds whose vendored `validate(input_data)` reads exactly one scalar
# field out of the input dict, this table lets `a1-validate <kind> <value>`
# accept a plain string from the shell and forward it as the right key.
# Multi-input validators are NOT in this table — they require a JSON object.
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


# One-liner description per validator — kept in sync with the README table.
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
# Typer app — single entry point for every subcommand.
# ---------------------------------------------------------------------------


app = typer.Typer(
    name="a1-validate",
    add_completion=False,
    no_args_is_help=True,
    cls=_CmdGroup,
    help=(
        "Validate Armenian / Russian IDs, chart-of-accounts codes, e-invoice "
        "shapes, payroll, and more — 23 SBOSS sovereign business-ops validators "
        "exposed as a single CLI. Run `a1-validate list` to see all kinds, "
        "or `a1-validate serve` to boot the HTTP service."
    ),
)


# ---------------------------------------------------------------------------
# --version flag — eager option on the root callback.
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"a1-validator {a1_validator.__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print a1-validator version and exit.",
    ),
) -> None:
    """Root callback — only handles `--version`."""
    pass


# ---------------------------------------------------------------------------
# Default-form validate (bound to the bare `a1-validate <kind> <value>` form
# via `_CmdGroup.parse_args`).
# ---------------------------------------------------------------------------


def _run_validate(kind: str, value: str) -> None:
    """Single-shot validate: resolve kind, coerce value, run validator, print JSON."""
    try:
        validator = a1_validator.get_validator(kind)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    try:
        payload = _coerce_value(kind, value)
    except typer.BadParameter as exc:
        typer.echo(f"error: {exc.message if hasattr(exc, 'message') else exc}", err=True)
        raise typer.Exit(code=1) from None

    try:
        result = validator(payload)
    except Exception as exc:  # pragma: no cover — defensive net
        typer.echo(f"error: validator {kind!r} raised {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=2) from None

    typer.echo(json.dumps(result, ensure_ascii=False))
    if isinstance(result, dict) and result.get("ok") is False:
        raise typer.Exit(code=1)


@app.command(name="__validate_default", hidden=True)
def __validate_default_cmd(
    kind: str = typer.Argument(..., help="Validator name (e.g. `hhvh`, `inn`)."),
    value: str | None = typer.Argument(
        None,
        help="Raw value or JSON object to validate. Optional so we can raise a "
             "friendly error instead of Click's stock `Missing argument 'VALUE'` "
             "(which would leak this internal sentinel command name).",
    ),
) -> None:
    """Hidden subcommand bound to the bare `a1-validate <kind> <value>` form.

    ``_CmdGroup.parse_args`` routes any non-subcommand invocation here, so the
    user-facing ``a1-validate hhvh 00123456`` syntax maps cleanly to this body.
    """
    if value is None:
        typer.echo(
            f"error: missing <value> for validator {kind!r}. "
            f"Usage: a1-validate {kind} <value>",
            err=True,
        )
        raise typer.Exit(code=1)
    _run_validate(kind, value)


# ---------------------------------------------------------------------------
# Explicit `validate <kind> <value>` subcommand — same body, non-hidden so
# `a1-validate validate hhvh 00123456` also works (useful for users who want
# to be explicit; mainly for tests and for the auto-generated help text).
# ---------------------------------------------------------------------------


@app.command()
def validate(
    kind: str = typer.Argument(..., help="Validator name (e.g. `hhvh`, `inn`)."),
    value: str = typer.Argument(..., help="Raw value or JSON object to validate."),
) -> None:
    """Validate a single value and print the result as JSON.

    The bare `a1-validate <kind> <value>` form is sugar for this command —
    ``_CmdGroup`` routes it here automatically. Most users will prefer the
    bare form; this explicit form is here for symmetry and so `a1-validate
    validate --help` shows the canonical CLI signature.
    """
    _run_validate(kind, value)


# ---------------------------------------------------------------------------
# `list` subcommand.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# `batch <kind> <file>` subcommand — supports BOTH plain-text (one value per
# line) and JSON eval-set (array of {input, expected}) inputs.
# ---------------------------------------------------------------------------


def _read_batch_inputs(path: Path) -> list[Any]:
    """Load a batch input file. Returns a list of dicts ready to feed a validator.

    Detection logic:
    - If the file's first non-whitespace char is ``[``, parse as JSON array.
      Each element is expected to be ``{"input": <dict>, "expected": <dict>}``;
      we return just the ``input`` dicts (the caller compares against expected).
    - Otherwise, treat as one value per line. Each non-blank line is wrapped
      under the validator's canonical single-string input key (see
      ``_SINGLE_INPUT_KEY``); there's no expected output to compare against,
      so the caller treats every line as "ok / not ok" based on the validator's
      ``ok`` field.
    """
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        # JSON eval-set — vendor-format array of {input, expected}.
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(
                f"{path}: JSON eval-set must be an array of {{input, expected}} "
                "objects, got " + type(data).__name__
            )
        return data
    # Plain text — one value per line.
    return [line for line in text.splitlines() if line.strip()]


@app.command()
def batch(
    kind: str = typer.Argument(..., help="Validator name (e.g. `hhvh`, `inn`)."),
    file: Path = typer.Argument(  # noqa: B008
        ...,
        help=(
            "Path to a batch input file. May be either (a) a JSON array of "
            "{input, expected} cases — the vendored eval-set shape — or (b) a "
            "plain-text file with one raw value per line."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Validate every case in a file and print a summary.

    The file may be either:
    * A JSON array of ``{input, expected}`` objects (the vendored eval-set
      shape — `tests/_eval_sets/<name>.json`). Each ``input`` is fed to
      ``a1_validator.<kind>(input)`` and the result is compared against
      ``expected`` under the same subset-equality contract as the pytest
      suite.
    * A plain-text file with one raw value per line. Each value is wrapped
      under the validator's canonical single-string input key and validated.
      No ``expected`` comparison — pass/fail is read from the validator's
      ``ok`` field.

    Exit code is 0 if every case matches, 1 otherwise. The summary prints
    total / ok / fail counts and lists every failing case with its input
    and the actual result.
    """
    try:
        validator = a1_validator.get_validator(kind)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    try:
        raw_cases = _read_batch_inputs(file)
    except json.JSONDecodeError as exc:
        typer.echo(f"error: {file} is not valid JSON: {exc}", err=True)
        raise typer.Exit(code=2) from None
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    # Detect mode: JSON eval-set (cases are dicts with "input") vs. plain text
    # (cases are raw strings).
    is_eval_set = bool(raw_cases) and isinstance(raw_cases[0], dict) and "input" in raw_cases[0]

    if is_eval_set:
        # Eval-set mode — each entry has {"input": ..., "expected": ...}.
        total = len(raw_cases)
        ok_count = 0
        failures: list[dict[str, Any]] = []
        for idx, case in enumerate(raw_cases):
            if not isinstance(case, dict) or "input" not in case:
                failures.append({"index": idx, "error": "case is not a dict with an 'input' field"})
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
    else:
        # Plain-text mode — entries are raw strings (one per line).
        if kind not in _SINGLE_INPUT_KEY:
            typer.echo(
                f"error: validator {kind!r} requires a JSON object input "
                f"(multiple fields), which can't be expressed one-per-line. "
                f"Pass --kind with a single-input validator or supply a JSON "
                f"eval-set file.",
                err=True,
            )
            raise typer.Exit(code=1)
        key = _SINGLE_INPUT_KEY[kind]
        total = len(raw_cases)
        ok_count = 0
        failures: list[dict[str, Any]] = []  # type: ignore[no-redef]
        for idx, raw_value in enumerate(raw_cases):
            payload = {key: raw_value}
            result = validator(payload)
            ok = isinstance(result, dict) and result.get("ok") is True
            if ok:
                ok_count += 1
            else:
                failures.append({
                    "index": idx,
                    "value": raw_value,
                    "result": result,
                })

    fail_count = total - ok_count
    typer.echo(json.dumps({
        "kind": kind,
        "file": str(file),
        "mode": "eval_set" if is_eval_set else "lines",
        "total": total,
        "ok": ok_count,
        "fail": fail_count,
        "failures": failures,
    }, ensure_ascii=False, indent=2))

    if fail_count > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# `serve` subcommand — owned by wip/http-service but included here so this
# cli.py is a superset of both branches. The orchestrator's merge can keep
# this file and drop http-service's cli.py without losing any subcommand.
#
# The import is deliberately lazy: `a1-validate --version` and the per-kind
# validate commands must not pay the cost of importing fastapi + uvicorn.
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        "-h",
        help="Bind host. Use 127.0.0.1 for loopback-only.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Bind port.",
        min=1,
        max=65535,
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload (development only).",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        help="Number of uvicorn worker processes.",
        min=1,
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        help="uvicorn log level (debug|info|warning|error|critical).",
    ),
) -> None:
    """Start the A1 Validator HTTP service.

    Boots the FastAPI app defined in ``a1_validator.server`` under
    ``uvicorn``. Use ``--reload`` during local development; production
    should set ``--workers`` and run behind a reverse proxy.
    """
    import uvicorn

    uvicorn.run(
        "a1_validator.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # uvicorn refuses --workers + --reload
        log_level=log_level,
    )


# ---------------------------------------------------------------------------
# Explicit `version` subcommand — companion to the `--version` flag. Both
# forms are useful: scripts prefer `--version` (machine-readable), humans
# prefer the subcommand.
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the a1-validator version."""
    typer.echo(f"a1-validator {a1_validator.__version__}")


__all__ = ["app"]
