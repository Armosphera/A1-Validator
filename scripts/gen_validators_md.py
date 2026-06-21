"""gen_validators_md.py — generate docs/validators.md from the live package API.

Run from the repo root:

    python scripts/gen_validators_md.py

Writes docs/validators.md. Committed alongside this script so the docs site
stays in sync with the source — re-run after adding or renaming a validator.

The script introspects the public API in three layers:

1. **Name + order** — `a1_validator.list_kinds()` returns the canonical 23
   names in the order they appear in `_port._VALIDATORS`. Adding a new
   validator to that table is the only change needed in source.
2. **Description** — from a small curated dict below. These mirror the
   one-liners in the README and are the human-authored layer above the
   introspection. Keys MUST match `list_kinds()`.
3. **Example input / output** — the first case in the corresponding
   `tests/_eval_sets/<kind>.json` file (the same vendored corpus that the
   pytest suite checks). The output is the *actual* result of running
   `a1_validator.<kind>(input)` against the installed package, so what
   you read in the docs is byte-for-byte what your installed library
   will return. The script runs each validator fresh in a fresh
   interpreter-style call — no caching, no fixtures.

If a validator is added without an entry in `VALIDATOR_DESCRIPTIONS`, the
script prints a warning and emits "(no description)" — the build does
not fail. CI runs this script before `mkdocs build --strict`, so a stale
description is loud but not blocking.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import a1_validator

# ---------------------------------------------------------------------------
# Curated descriptions — one line per validator.
#
# These mirror the README table. Keep them short (one sentence, < 100 chars
# ideally). Markdown link syntax is fine but avoid inline code blocks; the
# markdown renderer will pick up backticks and they'll read fine in mkdocs.
# ---------------------------------------------------------------------------
VALIDATOR_DESCRIPTIONS: dict[str, str] = {
    "hhvh": "Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ)",
    "inn": "Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (`ru-identifiers`)",
    "model_policy": "AI model-policy resolver (module → model)",
    "vat_return": "Armenian VAT return compute (sales/purchases → owed)",
    "payroll_am": "Armenian payroll compute (gross → taxes/net)",
    "chart_of_accounts_am": "Armenian chart-of-accounts lookup + validate (623 accounts)",
    "vat_return_form": "Armenian VAT-return form validation (line codes + amounts)",
    "phone_am": "Armenian phone NSN/E.164/format",
    "regions_am": "Armenian regions lookup (name/en/code → center)",
    "einvoice_am": "Armenian e-invoice structural validation",
    "chat_client": "OpenRouter chat client (mock-able HTTP transport)",
    "phone_ru": "Russian phone NSN/E.164/format",
    "ru_einvoice": "Russian e-invoice validate + XML build",
    "payroll_ru": "Russian payroll (NDFL, insurance, monthly ops)",
    "regions_ru": "Russian regions lookup (83 entries)",
    "chart_of_accounts_ru": "Russian chart-of-accounts lookup (73 accounts, 9 sections)",
    "vat_ru": "Russian VAT rate helpers + valid-rate check",
    "settings_store": "Local JSON settings store (read/write/list/delete)",
    "model_catalog": "OpenRouter model catalog fetch + normalize",
    "supplemental_sources": "Supplemental research sources normalizer",
    "open_notebook": "Notebook search/enable/normalize ops",
    "product_research": "Product-research config + program render + decide",
    "invoice": "Invoice field extractor (regex/mock, deterministic)",
    # 10 international business ID validators (v0.3.0)
    "eu_vat":      "EU VATIN (VAT identification number, 28 EU + GB/NO/CH)",
    "cnpj":        "Brazilian CNPJ (14 digits, mod-11 DV per Receita Federal)",
    "cpf":         "Brazilian CPF (11 digits, mod-11 DV per Receita Federal)",
    "uk_company":  "UK Company Number (8 digits, or SC/NI/OC/SO + 6 digits)",
    "us_ein":      "US EIN (9 digits, IRS campus code prefix)",
    "gstin":       "India GSTIN (15 alphanumeric, state code + PAN + Z + check)",
    "swiss_uid":   "Swiss UID (CHE/CH/CDF + 9 digits)",
    "au_abn":      "Australian Business Number (11 digits, mod-89 check)",
    "mx_rfc":      "Mexico RFC (12-13 chars, SAT mod-11 verification digit)",
    "jp_mynumber": "Japan My Number (12 digits, mod-11 check, 個人番号)",
    # 4 more international business ID validators (v0.4.0)
    "ar_cuit":     "Argentina CUIT/CUIL (11 digits, AFIP mod-11)",
    "cl_rut":      "Chile RUT (7-8 digits + check, SII mod-11 right-to-left)",
    "sg_uen":      "Singapore UEN (9-10 alphanumeric, ACRA-internal check letter)",
    "kr_brn":      "Korea BRN (10 digits, 3-2-5 format, NTS structural)",
}



# ---------------------------------------------------------------------------
# IO paths.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EVAL_SETS_DIR = REPO_ROOT / "tests" / "_eval_sets"
OUTPUT_PATH = REPO_ROOT / "docs" / "validators.md"


def _load_example_input(kind: str) -> tuple[Any, str]:
    """Return (input, source_label) for the kind's first eval-set case.

    Falls back to `("<see docs>", "(no vendored eval set)")` when the file
    is missing — this lets the docs build still succeed if a new validator
    hasn't shipped its eval corpus yet. The build is non-fatal; CI will
    see a degraded row but not a failure.
    """
    eval_path = EVAL_SETS_DIR / f"{kind}.json"
    if not eval_path.exists():
        return "<see docs>", "(no vendored eval set)"
    with eval_path.open() as fp:
        cases = json.load(fp)
    if not cases:
        return "<see docs>", "(empty eval set)"
    return cases[0]["input"], eval_path.name


def _run_validator(kind: str, input_data: Any) -> Any:
    """Dispatch through `a1_validator.validate(kind, value)` — same path as
    the CLI / HTTP service / public dispatcher. Exceptions are caught and
    returned as `{"error": "<class>: <message>"}` so a broken validator
    can't break the docs build.
    """
    try:
        return a1_validator.validate(kind, input_data)
    except Exception as exc:  # pragma: no cover — defensive net for docs
        return {"error": f"{type(exc).__name__}: {exc}"}


def _format_json(obj: Any, *, indent: int = 2) -> str:
    r"""Pretty-print a JSON snippet with stable key order. Use `ensure_ascii=False`
    so the Armenian / Russian strings (ՀՎՀՀ, ИНН) stay readable in the docs
    rather than turning into `\uXXXX` escapes.
    """
    return json.dumps(obj, indent=indent, ensure_ascii=False, sort_keys=True)


def _truncate(text: str, *, limit: int = 1200) -> str:
    """Long example inputs (the `invoice` validator embeds a 600-char
    document blob) blow up the rendered page. Truncate with a marker.
    """
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n  ... (truncated — full input in vendored eval-set)"


def render_table() -> str:
    """Build the markdown body for docs/validators.md."""
    kinds = a1_validator.list_kinds()
    assert len(kinds) >= 23, (
        f"Expected >= 23 validators, got {len(kinds)}. "
        f"Did you forget to add a row to _port._VALIDATORS?"
    )

    lines: list[str] = []
    lines.append("# Validators")
    lines.append("")
    lines.append(
        "Auto-generated reference for every public validator in `a1_validator`. "
        "The table below covers all 23 kinds in their canonical order; per-kind "
        "sections below show a real example input (lifted from the vendored "
        "`tests/_eval_sets/<kind>.json` corpus) and the actual dict returned "
        "by the installed library — re-run `python scripts/gen_validators_md.py` "
        "after editing the package to refresh this page."
    )
    lines.append("")

    # ---- Summary table ----
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Kind | Description | Input shape |")
    lines.append("| - | ---- | ----------- | ----------- |")
    for idx, kind in enumerate(kinds, start=1):
        description = VALIDATOR_DESCRIPTIONS.get(kind, "(no description)")
        model = a1_validator.model_for(kind)
        # The model exposes the fields the validator reads from `input_data`.
        # Cheap shape summary — accurate enough for a docs table.
        field_names = ", ".join(sorted(model.model_fields.keys()))
        # Markdown cell — escape pipes in description.
        description_cell = description.replace("|", "\\|")
        lines.append(f"| {idx} | `{kind}` | {description_cell} | `{field_names}` |")
    lines.append("")

    # ---- Per-kind sections ----
    lines.append("## Per-kind reference")
    lines.append("")
    for idx, kind in enumerate(kinds, start=1):
        description = VALIDATOR_DESCRIPTIONS.get(kind, "(no description)")
        example_input, source = _load_example_input(kind)
        example_output = _run_validator(kind, example_input)

        lines.append(f"### {idx}. `{kind}`")
        lines.append("")
        lines.append(f"**{description}**")
        lines.append("")
        lines.append(f"- **Aliases**: {', '.join(a1_validator._port._VALIDATORS[idx-1][2]) or '—'}")
        lines.append(f"- **Example source**: `{source}`")
        # Pull the actual class name from the Pydantic model — the
        # kind→classname mapping has irregular cases (`hhvh` → `HHVH`,
        # `model_policy` → `ModelPolicy`) that a generic snake-to-Camel
        # conversion can't reproduce. `model_for(...).__name__` is the
        # single source of truth.
        model_name = a1_validator.model_for(kind).__name__
        lines.append(f"- **Pydantic result model**: `a1_validator.{model_name}`")
        lines.append("")
        lines.append("**Example input**")
        lines.append("")
        lines.append("```json")
        lines.append(_truncate(_format_json(example_input)))
        lines.append("```")
        lines.append("")
        lines.append("**Example output**")
        lines.append("")
        lines.append("```json")
        lines.append(_truncate(_format_json(example_output)))
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    body = render_table()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(body, encoding="utf-8")
    kinds = a1_validator.list_kinds()
    print(f"wrote {OUTPUT_PATH} ({len(body)} bytes, {len(kinds)} validators)")
    # Loud-but-non-fatal warnings for missing descriptions — easy to grep.
    missing = [k for k in kinds if k not in VALIDATOR_DESCRIPTIONS]
    if missing:
        print(f"WARNING: missing descriptions in VALIDATOR_DESCRIPTIONS: {missing}")


if __name__ == "__main__":
    main()
