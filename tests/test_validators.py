"""Pytest suite for the 33 SBOSS sovereign business ID validators vendored under a1_validator.

Each ``test_<name>`` function loads ``tests/_eval_sets/<name>.json`` (a
verbatim copy of the upstream autoresearch-sboss eval_set.json) and asserts
that ``a1_validator.<name>(input)`` returns a dict that matches the
expected one.

Matching contract — mirrors the upstream autoresearch-sboss score function:

1. **Subset equality**: every key in ``expected`` must be present in
   ``actual`` with a matching value. Extra keys in ``actual`` are allowed
   (they reflect internal state the validator exposes for diagnostics,
   e.g. ``last_request``, ``operation``, ``endpoint`` in chat_client).

2. **Dotted-path keys**: ``expected`` may contain dotted keys like
   ``last_request.method`` — these are interpreted as nested lookups
   against ``actual`` (``actual["last_request"]["method"]``). This mirrors
   the upstream eval-set convention.

3. **Float tolerance**: ``expected`` float values match ``actual`` floats
   within ``pytest.approx`` (default 1e-6 relative tolerance). This avoids
   false negatives from binary-float arithmetic in payroll/vat/product
   calculations.

Notes on coverage:
- ``tests/_eval_sets/inn.json`` and ``tests/_eval_sets/ru_identifiers.json``
  are byte-identical (both test ``a1_validator.inn`` — the public alias for
  the vendored ``ru_identifiers`` module). We test against ``inn.json`` and
  skip the duplicate.
- ``settings_store`` is a stateful file-backed store — each parametrize
  case runs against a fresh ``tmp_path`` so cases don't leak state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import a1_validator

# `tests/_eval_sets/` sits next to this test file.
_TESTS_DIR = Path(__file__).resolve().parent
_EVAL_SETS_DIR = _TESTS_DIR / "_eval_sets"


# ---------------------------------------------------------------------------
# Matching contract — subset equality with dotted-path + float tolerance.
# ---------------------------------------------------------------------------


def _matches(actual, expected) -> bool:
    """Return True iff ``actual`` matches ``expected`` under the A1 contract.

    Contract:
    - Dicts: every key in ``expected`` must be in ``actual`` (extra keys
      in ``actual`` are allowed); nested dicts recurse.
    - Dotted keys (e.g. ``"last_request.method"``): traverse into the
      nested actual dict.
    - Floats: ``pytest.approx`` comparison.
    - All other scalars / lists: exact ``==``.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if isinstance(k, str) and "." in k:
                # Dotted-path key — descend into actual.
                cur = actual
                for part in k.split("."):
                    if isinstance(cur, dict) and part in cur:
                        cur = cur[part]
                    else:
                        return False
                if not _matches(cur, v):
                    return False
            else:
                if k not in actual or not _matches(actual[k], v):
                    return False
        return True
    if isinstance(expected, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        return actual == pytest.approx(expected)
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_matches(a, e) for a, e in zip(actual, expected, strict=False))
    return actual == expected


def _make_cases(validator_name: str) -> list[pytest.param]:
    """Build a ``pytest.param`` list for one validator's vendored eval_set."""
    with (_EVAL_SETS_DIR / f"{validator_name}.json").open(encoding="utf-8") as f:
        eval_set = json.load(f)

    def _id_for(i: int, case: dict) -> str:
        inp = case.get("input", {})
        if isinstance(inp, dict):
            for v in inp.values():
                if isinstance(v, (str, int, float, bool)):
                    return f"case{i}-{v!s}"[:40]
        return f"case{i}"

    return [
        pytest.param(case["input"], case["expected"], id=_id_for(i, case))
        for i, case in enumerate(eval_set)
    ]


# ---------------------------------------------------------------------------
# 23 parametrized validator tests — one per public validator function.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("input_data, expected", _make_cases("hhvh"))
def test_hhvh(input_data, expected):
    assert _matches(a1_validator.hhvh(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("inn"))
def test_inn(input_data, expected):
    """a1_validator.inn is the public alias for the ru_identifiers module."""
    assert _matches(a1_validator.inn(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("model_policy"))
def test_model_policy(input_data, expected):
    assert _matches(a1_validator.model_policy(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("vat_return"))
def test_vat_return(input_data, expected):
    assert _matches(a1_validator.vat_return(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("payroll_am"))
def test_payroll_am(input_data, expected):
    assert _matches(a1_validator.payroll_am(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("chart_of_accounts_am"))
def test_chart_of_accounts_am(input_data, expected):
    assert _matches(a1_validator.chart_of_accounts_am(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("vat_return_form"))
def test_vat_return_form(input_data, expected):
    assert _matches(a1_validator.vat_return_form(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("phone_am"))
def test_phone_am(input_data, expected):
    assert _matches(a1_validator.phone_am(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("regions_am"))
def test_regions_am(input_data, expected):
    assert _matches(a1_validator.regions_am(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("einvoice_am"))
def test_einvoice_am(input_data, expected):
    assert _matches(a1_validator.einvoice_am(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("chat_client"))
def test_chat_client(input_data, expected):
    assert _matches(a1_validator.chat_client(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("phone_ru"))
def test_phone_ru(input_data, expected):
    assert _matches(a1_validator.phone_ru(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("ru_einvoice"))
def test_ru_einvoice(input_data, expected):
    assert _matches(a1_validator.ru_einvoice(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("payroll_ru"))
def test_payroll_ru(input_data, expected):
    assert _matches(a1_validator.payroll_ru(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("regions_ru"))
def test_regions_ru(input_data, expected):
    assert _matches(a1_validator.regions_ru(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("chart_of_accounts_ru"))
def test_chart_of_accounts_ru(input_data, expected):
    assert _matches(a1_validator.chart_of_accounts_ru(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("vat_ru"))
def test_vat_ru(input_data, expected):
    assert _matches(a1_validator.vat_ru(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("settings_store"))
def test_settings_store(input_data, expected, tmp_path):
    """settings_store is stateful — each case gets a fresh tmp_path."""
    # The vendored validate() reads/writes a JSON file under dataDir. Inject
    # a fresh directory per case so multi-op sequences don't leak state.
    injected = {**input_data, "dataDir": str(tmp_path)}
    assert _matches(a1_validator.settings_store(injected), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("model_catalog"))
def test_model_catalog(input_data, expected):
    assert _matches(a1_validator.model_catalog(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("supplemental_sources"))
def test_supplemental_sources(input_data, expected):
    assert _matches(a1_validator.supplemental_sources(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("open_notebook"))
def test_open_notebook(input_data, expected):
    assert _matches(a1_validator.open_notebook(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("product_research"))
def test_product_research(input_data, expected):
    assert _matches(a1_validator.product_research(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("invoice"))
def test_invoice(input_data, expected):
    assert _matches(a1_validator.invoice(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("eu_vat"))
def test_eu_vat(input_data, expected):
    assert _matches(a1_validator.eu_vat(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("cnpj"))
def test_cnpj(input_data, expected):
    assert _matches(a1_validator.cnpj(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("cpf"))
def test_cpf(input_data, expected):
    assert _matches(a1_validator.cpf(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("uk_company"))
def test_uk_company(input_data, expected):
    assert _matches(a1_validator.uk_company(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("us_ein"))
def test_us_ein(input_data, expected):
    assert _matches(a1_validator.us_ein(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("gstin"))
def test_gstin(input_data, expected):
    assert _matches(a1_validator.gstin(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("swiss_uid"))
def test_swiss_uid(input_data, expected):
    assert _matches(a1_validator.swiss_uid(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("au_abn"))
def test_au_abn(input_data, expected):
    assert _matches(a1_validator.au_abn(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("mx_rfc"))
def test_mx_rfc(input_data, expected):
    assert _matches(a1_validator.mx_rfc(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("jp_mynumber"))
def test_jp_mynumber(input_data, expected):
    assert _matches(a1_validator.jp_mynumber(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("ar_cuit"))
def test_ar_cuit(input_data, expected):
    assert _matches(a1_validator.ar_cuit(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("cl_rut"))
def test_cl_rut(input_data, expected):
    assert _matches(a1_validator.cl_rut(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("sg_uen"))
def test_sg_uen(input_data, expected):
    assert _matches(a1_validator.sg_uen(input_data), expected)


@pytest.mark.parametrize("input_data, expected", _make_cases("kr_brn"))
def test_kr_brn(input_data, expected):
    assert _matches(a1_validator.kr_brn(input_data), expected)


# ---------------------------------------------------------------------------
# Meta-tests: dispatcher + canonical-name enumeration + model_for() path.
# ---------------------------------------------------------------------------


def test_list_kinds_returns_23_canonical_names():
    kinds = a1_validator.list_kinds()
    assert len(kinds) == 37
    assert kinds[0] == "hhvh"
    assert kinds[-1] == "kr_brn"
    # No alias leakage into the canonical list.
    assert "identifier" not in kinds
    assert "ru_identifiers" not in kinds


def test_public_symbols_count():
    """The package must expose at least 25 public symbols."""
    public = [x for x in dir(a1_validator) if not x.startswith("_")]
    assert len(public) >= 25, f"expected >=25, got {len(public)}: {public}"


def test_dispatcher_dispatches_each_canonical_kind():
    """a1_validator.validate(kind, value) must match a1_validator.<kind>(value)."""
    sample_inputs = {
        "hhvh": {"hvhh": "00123456"},
        "inn": {"id": "7707083893"},
        "model_policy": {"policy": {"default": "anthropic/claude-3.5-sonnet"}, "ctx": {}},
        "phone_am": {"phone": "+37491234567"},
        "phone_ru": {"value": "+7 (495) 123-45-67"},
        "regions_am": {"query": "AM-ER"},
        "regions_ru": {"query": "RU-MOW"},
        "vat_ru": {"operation": "ratesFor", "year": 2026},
    }
    for kind, value in sample_inputs.items():
        expected = getattr(a1_validator, kind)(value)
        assert a1_validator.validate(kind, value) == expected, f"mismatch on {kind}"


def test_dispatcher_accepts_inn_aliases():
    """`inn`, `identifier`, and `ru_identifiers` all dispatch to the same function."""
    value = {"id": "7707083893"}
    expected = a1_validator.inn(value)
    assert a1_validator.validate("identifier", value) == expected
    assert a1_validator.validate("ru_identifiers", value) == expected


def test_dispatcher_raises_on_unknown_kind():
    with pytest.raises(KeyError, match="Unknown validator kind"):
        a1_validator.validate("not_a_real_validator", {})


def test_model_for_returns_typed_model():
    """a1_validator.model_for(kind).model_validate(result) coerces the dict result."""
    import pydantic

    kind = "hhvh"
    result = a1_validator.validate(kind, {"hvhh": "00123456"})
    Model = a1_validator.model_for(kind)
    assert issubclass(Model, pydantic.BaseModel)
    parsed = Model.model_validate(result)
    assert parsed.ok is True
    assert parsed.normalized == "00123456"


def test_model_for_raises_on_unknown_kind():
    with pytest.raises(KeyError, match="No result model"):
        a1_validator.model_for("nope")
