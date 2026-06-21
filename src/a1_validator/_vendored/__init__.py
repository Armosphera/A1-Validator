"""_vendored — vendored copies of autoresearch-sboss workflow.py modules.

This subpackage contains the 23 SBOSS sovereign business ID validators,
vendored from autoresearch-sboss@6c9a9149f1dc8b7a5430d542de19f564a078418c.
Each module exposes a uniform `validate(input_data)` function (the original
`run_workflow` adapter has been renamed) and is loaded lazily by `_port.py`.

Re-running `python scripts/_vendor.py` after pulling upstream regenerates
this directory from the upstream source — do not edit by hand.

Upstream source: https://github.com/Armosphera/autoresearch-sboss
License: MIT
"""

from __future__ import annotations

from . import (
    ar_cuit,
    au_abn,
    chart_of_accounts_am,
    chart_of_accounts_ru,
    chat_client,
    cl_rut,
    cnpj,
    cpf,
    einvoice_am,
    eu_vat,
    gstin,
    hhvh,
    il_id,
    in_pan,
    invoice,
    jp_mynumber,
    kr_brn,
    model_catalog,
    model_policy,
    mx_rfc,
    open_notebook,
    payroll_am,
    payroll_ru,
    phone_am,
    phone_ru,
    product_research,
    regions_am,
    regions_ru,
    ru_einvoice,
    ru_identifiers,
    sa_tin,
    settings_store,
    sg_uen,
    supplemental_sources,
    swiss_uid,
    tw_ubn,
    uk_company,
    us_ein,
    vat_return,
    vat_return_form,
    vat_ru,
)

__all__ = [
    "ar_cuit",
    "au_abn",
    "chart_of_accounts_am",
    "chart_of_accounts_ru",
    "chat_client",
    "cl_rut",
    "cnpj",
    "cpf",
    "einvoice_am",
    "eu_vat",
    "gstin",
    "hhvh",
    "il_id",
    "in_pan",
    "invoice",
    "jp_mynumber",
    "kr_brn",
    "model_catalog",
    "model_policy",
    "mx_rfc",
    "open_notebook",
    "payroll_am",
    "payroll_ru",
    "phone_am",
    "phone_ru",
    "product_research",
    "regions_am",
    "regions_ru",
    "ru_einvoice",
    "ru_identifiers",
    "sa_tin",
    "settings_store",
    "sg_uen",
    "supplemental_sources",
    "swiss_uid",
    "tw_ubn",
    "uk_company",
    "us_ein",
    "vat_return",
    "vat_return_form",
    "vat_ru",
]