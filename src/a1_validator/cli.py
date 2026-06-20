"""cli.py — `a1-validate` command-line interface.

This module exposes a single Typer ``app`` object that is registered as the
``a1-validate`` console script in ``pyproject.toml``.

Subcommands:

  * ``a1-validate serve [--host 0.0.0.0] [--port 8000] [--reload]`` — start
    the FastAPI HTTP service (this module is the only owner of that
    subcommand). Uses ``uvicorn`` under the hood.
  * ``a1-validate --version`` / ``a1-validate version`` — print
    ``a1_validator.__version__``.

The CLI is intentionally tiny. Other subcommands (``list``, ``batch``, …)
are added by sibling tasks in this plan; the merge in the
``packaging-and-deploy`` phase combines them.
"""

from __future__ import annotations

import typer

import a1_validator

# The single entry point Typer app. pyproject.toml wires
# `a1-validate = a1_validator.cli:app`.
app = typer.Typer(
    name="a1-validate",
    help="A1 Validator — 23 SBOSS sovereign business ID validators.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)


def _version_callback(value: bool) -> None:
    """Print the package version and exit when ``--version`` is passed."""
    if value:
        typer.echo(a1_validator.__version__)
        raise typer.Exit(code=0)


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        help="Print the a1-validator version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Top-level options shared by every subcommand."""


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
    # Imported lazily so `a1-validate --version` doesn't pay the cost of
    # importing fastapi + uvicorn (which is non-trivial).
    import uvicorn

    uvicorn.run(
        "a1_validator.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # uvicorn refuses --workers + --reload
        log_level=log_level,
    )


@app.command(name="version")
def version_cmd() -> None:
    """Print the a1-validator version."""
    typer.echo(a1_validator.__version__)


if __name__ == "__main__":
    app()
