"""A1 Validator — 23 SBOSS sovereign business ID validators.

A faithful Python port of the workflow validators published in
[autoresearch-sboss](https://github.com/Armosphera/autoresearch-sboss).
Each validator is a thin re-export of the corresponding vendored module's
`validate(input_data)` function — see `a1_validator._port` and
`a1_validator._vendored` for the wiring.

Quick start:
    >>> import a1_validator
    >>> a1_validator.hhvh({"hvhh": "00123456"})
    {'ok': True, 'normalized': '00123456', 'error': None}

    >>> a1_validator.inn({"id": "7707083893"})
    {'ok': True, 'normalized': '7707083893', 'kind': 'inn', 'error': None}

    >>> a1_validator.validate("hhvh", {"hvhh": "00123456"})
    {'ok': True, 'normalized': '00123456', 'error': None}
"""

from __future__ import annotations

# Import the result-model submodule via `importlib` to avoid leaking the
# `results` name into our public namespace (the underscore-prefix alias
# doesn't help — `from . import results` puts `results` into sys.modules
# and Python exposes it as an attribute of this package).
import importlib as _importlib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

_results = _importlib.import_module("a1_validator.results")

__version__ = "0.0.0+local"  # overridden below from package metadata
try:
    __version__ = _pkg_version("a1-validator")
except PackageNotFoundError:
    # Package not installed (e.g. running from a source checkout) — fall
    # back to the sentinel above. CI / publish always installs the
    # wheel, so this branch only matters for `python -c 'import ...'`
    # from a git clone.
    pass

from ._port import (  # noqa: E402
    _VALIDATE_TABLE,
    _VALIDATORS,
    get_validator,
    list_kinds,
)

# ---------------------------------------------------------------------------
# Re-export each vendored validator as a top-level A1-Validator function.
# ---------------------------------------------------------------------------
# `_VALIDATORS` is the single source of truth — entries are
# (public_name, vendored_module_name, kind_aliases). Adding a new validator
# is one line in `_port._VALIDATORS`.
for _public_name, _module_name, _aliases in _VALIDATORS:
    _validate_fn = getattr(__import__("a1_validator._vendored", fromlist=[_module_name]), _module_name).validate
    globals()[_public_name] = _validate_fn


# ---------------------------------------------------------------------------
# Unified dispatcher: a1_validator.validate(kind, value) -> dict
# ---------------------------------------------------------------------------

def validate(kind: str, value: Any) -> dict[str, Any]:
    """Run the named validator on `value` and return its dict result.

    Args:
        kind: One of the 23 canonical validator names (e.g. "hhvh", "inn",
            "invoice") or an alias (e.g. "identifier" → ru_identifiers).
        value: The validator-specific input dict (e.g. {"hvhh": "00123456"}).

    Returns:
        The validator's dict result. Shape depends on `kind` — see the
        matching Pydantic model in `a1_validator.results` for the contract.

    Raises:
        KeyError: If `kind` is not a known validator name.
    """
    fn = get_validator(kind)
    return fn(value)


# Snapshot the result-models mapping and the common base class before we
# `del _results` at the bottom of this module — the closures in `model_for`
# (and the `HHVHResult`/etc. re-exports below) need to keep working even
# after the import-module reference is dropped from the public namespace.
_RESULT_MODELS: dict[str, type[_BaseResult]] = _results.RESULT_MODELS  # type: ignore[valid-type]
_BaseResult = _results._BaseResult


def model_for(kind: str) -> type[_BaseResult]:  # type: ignore[valid-type]
    """Return the Pydantic v2 result model for the named validator.

    Useful for typed consumers:
        >>> result = a1_validator.validate("hhvh", {"hvhh": "00123456"})
        >>> a1_validator.model_for("hhvh").model_validate(result)
        HHVHResult(ok=True, normalized='00123456', error=None)
    """
    try:
        return _RESULT_MODELS[kind]
    except KeyError as exc:
        raise KeyError(
            f"No result model for validator kind {kind!r}. Known kinds: "
            f"{sorted(_RESULT_MODELS.keys())}"
        ) from exc


# Convenience re-exports — the 23 Pydantic models are accessible as
# `a1_validator.HHVHResult`, `a1_validator.INNResult`, etc.
for _model_name in dir(_results):
    if _model_name.endswith("Result") and not _model_name.startswith("_"):
        globals()[_model_name] = getattr(_results, _model_name)


__all__ = [
    # 23 validator functions
    "hhvh", "inn", "model_policy", "vat_return", "payroll_am",
    "chart_of_accounts_am", "vat_return_form", "phone_am", "regions_am",
    "einvoice_am", "chat_client", "phone_ru", "ru_einvoice", "payroll_ru",
    "regions_ru", "chart_of_accounts_ru", "vat_ru", "settings_store",
    "model_catalog", "supplemental_sources", "open_notebook",
    "product_research", "invoice",
    # Dispatcher + helpers
    "validate", "model_for", "list_kinds", "get_validator",
    "RESULTS", "RESULT_MODELS",
    # 23 Pydantic models (re-exported from .results)
    "HHVHResult", "INNResult", "ModelPolicyResult", "VatReturnResult",
    "PayrollAmResult", "ChartOfAccountsAmResult", "VatReturnFormResult",
    "PhoneAmResult", "RegionsAmResult", "EInvoiceAmResult",
    "ChatClientResult", "PhoneRuResult", "RuEInvoiceResult", "PayrollRuResult",
    "RegionsRuResult", "ChartOfAccountsRuResult", "VatRuResult",
    "SettingsStoreResult", "ModelCatalogResult", "SupplementalSourcesResult",
    "OpenNotebookResult", "ProductResearchResult", "InvoiceResult",
    "__version__",
]

# Alias for the result-model dict (mirrors the module-level RESULT_MODELS).
RESULTS = _results.RESULT_MODELS

# Use __all__ to control what `from a1_validator import *` exports — keep the
# leak surface tight (no typing helpers, no submodule references).
del _results
del _VALIDATORS
del _VALIDATE_TABLE

# Python exposes submodules as attributes of their parent package. Drop the
# `results` reference so `dir(a1_validator)` only shows the public surface
# declared in `__all__`.
import sys as _sys  # noqa: E402

_sys.modules[__name__].__dict__.pop("results", None)
