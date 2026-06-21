"""_port.py — re-export each vendored validator's `validate` function as the
A1-Validator package's per-name entry point.

Each vendored module under `_vendored/<name>.py` exposes a uniform `validate(input_data)`
function (the original `run_workflow` adapter has been renamed). This module
re-exports those functions under a flat namespace keyed by the validator's
public name (e.g. `_port.hhvh` = `_vendored.hhvh.validate`).

`__init__.py` then re-exports each as `a1_validator.<name>` and wires up the
Pydantic v2 result models + the unified `a1_validator.validate(kind, value)`
dispatcher.

The 23 mappings are declarative — adding a new validator is a single line.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import _vendored

# (public_name, vendored_module_name, kind_aliases)
# kind_aliases are the alternative names accepted by `a1_validator.validate(kind, value)`
# (e.g. `a1_validator.validate("inn", ...)` dispatches to the ru_identifiers module).
_VALIDATORS: list[tuple[str, str, tuple[str, ...]]] = [
    ("hhvh",                 "hhvh",                 ()),
    ("inn",                  "ru_identifiers",       ("identifier", "ru_identifiers")),
    ("model_policy",         "model_policy",         ()),
    ("vat_return",           "vat_return",           ()),
    ("payroll_am",           "payroll_am",           ()),
    ("chart_of_accounts_am", "chart_of_accounts_am", ()),
    ("vat_return_form",      "vat_return_form",      ()),
    ("phone_am",             "phone_am",             ()),
    ("regions_am",           "regions_am",           ()),
    ("einvoice_am",          "einvoice_am",          ()),
    ("chat_client",          "chat_client",          ()),
    ("phone_ru",             "phone_ru",             ()),
    ("ru_einvoice",          "ru_einvoice",          ()),
    ("payroll_ru",           "payroll_ru",           ()),
    ("regions_ru",           "regions_ru",           ()),
    ("chart_of_accounts_ru", "chart_of_accounts_ru", ()),
    ("vat_ru",               "vat_ru",               ()),
    ("settings_store",       "settings_store",       ()),
    ("model_catalog",        "model_catalog",        ()),
    ("supplemental_sources", "supplemental_sources", ()),
    ("open_notebook",        "open_notebook",        ()),
    ("product_research",     "product_research",     ()),
    ("invoice",              "invoice",              ()),
    # 10 international business ID validators (added in v0.3.0)
    ("eu_vat",               "eu_vat",               ()),
    ("cnpj",                 "cnpj",                 ()),
    ("cpf",                  "cpf",                  ()),
    ("uk_company",           "uk_company",           ()),
    ("us_ein",               "us_ein",               ()),
    ("gstin",                "gstin",                ()),
    ("swiss_uid",            "swiss_uid",            ()),
    ("au_abn",               "au_abn",               ()),
    ("mx_rfc",               "mx_rfc",               ()),
    ("jp_mynumber",          "jp_mynumber",          ()),
]


def _build_port_table() -> dict[str, Callable[[Any], dict[str, Any]]]:
    """Construct the name → validate() mapping at import time."""
    table: dict[str, Callable[[Any], dict[str, Any]]] = {}
    for public_name, module_name, aliases in _VALIDATORS:
        mod = getattr(_vendored, module_name)
        validate_fn = mod.validate
        table[public_name] = validate_fn
        for alias in aliases:
            table[alias] = validate_fn
    return table


# Populated at module-import time. The lazy build lets the package import even
# if a vendored module has an unrelated top-level error (we want a clean error
# surface for diagnostics).
_VALIDATE_TABLE: dict[str, Callable[[Any], dict[str, Any]]] = _build_port_table()


def get_validator(name: str) -> Callable[[Any], dict[str, Any]]:
    """Look up a validator by name. Raises KeyError on unknown kind."""
    try:
        return _VALIDATE_TABLE[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown validator kind {name!r}. Known kinds: "
            f"{sorted(set(_VALIDATE_TABLE.keys()))}"
        ) from exc


def list_kinds() -> list[str]:
    """Return the canonical 23 validator names (no aliases)."""
    return [name for name, _, _ in _VALIDATORS]


__all__ = [
    "get_validator",
    "list_kinds",
    "_VALIDATORS",
    "_VALIDATE_TABLE",
]
