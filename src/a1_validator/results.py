"""results.py — Pydantic v2 result models for each of the 23 validators.

One model per validator, named to match the public validator function
(`HHVHResult` ↔ `a1_validator.hhvh`, `INNResult` ↔ `a1_validator.inn`, etc.).
All models use `extra="allow"` so future field additions don't break existing
code, and every field defaults to None unless the eval corpus pins it.

These models are also useful as TypeScript-style shape contracts for downstream
consumers (e.g. SBOSS UI forms, finance close reports). Validation is
intentionally lenient — `model_validate(...)` will not raise if the dict has
extra fields or missing optional fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _BaseResult(BaseModel):
    """Common config: allow extras, suppress unknown-field warnings."""

    model_config = ConfigDict(extra="allow", frozen=False)


# ---------------------------------------------------------------------------
# 23 result models — one per validator.
# ---------------------------------------------------------------------------


class HHVHResult(_BaseResult):
    """Output of `a1_validator.hhvh()`."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class INNResult(_BaseResult):
    """Output of `a1_validator.inn()` — Russian identifier dispatcher."""

    ok: bool | None = None
    normalized: str | None = None
    kind: str | None = None
    error: str | None = None


class ModelPolicyResult(_BaseResult):
    """Output of `a1_validator.model_policy()`."""

    resolved_model: str | None = None
    source: str | None = None


class VatReturnResult(_BaseResult):
    """Output of `a1_validator.vat_return()`."""

    net: float | None = None
    outputVat: float | None = None
    inputVat: float | None = None
    payable: float | None = None
    creditCarried: float | None = None
    taxableSales: float | None = None
    taxablePurchases: float | None = None


class PayrollAmResult(_BaseResult):
    """Output of `a1_validator.payroll_am()`."""

    gross: float | None = None
    incomeTax: float | None = None
    pension: float | None = None
    healthInsurance: float | None = None
    stampDuty: float | None = None
    totalWithholdings: float | None = None
    net: float | None = None


class ChartOfAccountsAmResult(_BaseResult):
    """Output of `a1_validator.chart_of_accounts_am()`."""

    code: Any | None = None
    ok: bool | None = None
    normalized: str | None = None
    hy: str | None = None
    class_: int | None = None  # `class` is a Python keyword — use the alias.
    type: str | None = None
    error: str | None = None

    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Map incoming `class` key to `class_` field.
        if isinstance(obj, dict) and "class" in obj and "class_" not in obj:
            obj = {**obj, "class_": obj["class"]}
        return super().model_validate(obj, *args, **kwargs)


class VatReturnFormResult(_BaseResult):
    """Output of `a1_validator.vat_return_form()`."""

    ok: bool | None = None
    error_count: int | None = None
    error_codes: list[str] | None = None


class PhoneAmResult(_BaseResult):
    """Output of `a1_validator.phone_am()`."""

    nsn: str | None = None
    valid: bool | None = None
    e164: str | None = None
    formatted: str | None = None


class RegionsAmResult(_BaseResult):
    """Output of `a1_validator.regions_am()`."""

    found: bool | None = None
    code: str | None = None
    hy: str | None = None
    en: str | None = None
    center: str | None = None


class EInvoiceAmResult(_BaseResult):
    """Output of `a1_validator.einvoice_am()`."""

    ok: bool | None = None
    error_count: int | None = None
    error_codes: list[str] | None = None


class ChatClientResult(_BaseResult):
    """Output of `a1_validator.chat_client()`."""

    ok: bool | None = None
    model: str | None = None
    provider: str | None = None
    text: str | None = None
    responseId: str | None = None
    error_code: str | None = None
    error_status: int | None = None
    last_request: dict[str, Any] | None = None


class PhoneRuResult(_BaseResult):
    """Output of `a1_validator.phone_ru()`."""

    nsn: str | None = None
    valid: bool | None = None
    e164: str | None = None
    formatted: str | None = None


class RuEInvoiceResult(_BaseResult):
    """Output of `a1_validator.ru_einvoice()`."""

    ok: bool | None = None
    error_count: int | None = None
    error_codes: list[str] | None = None


class PayrollRuResult(_BaseResult):
    """Output of `a1_validator.payroll_ru()` — generic {result: ...} wrapper."""

    result: Any | None = None


class RegionsRuResult(_BaseResult):
    """Output of `a1_validator.regions_ru()`."""

    found: bool | None = None
    code: str | None = None
    ru: str | None = None
    en: str | None = None
    center: str | None = None


class ChartOfAccountsRuResult(_BaseResult):
    """Output of `a1_validator.chart_of_accounts_ru()`."""

    found: bool | None = None
    code: str | None = None
    ru: str | None = None
    section: str | None = None
    nature: str | None = None
    normalBalance: str | None = None


class VatRuResult(_BaseResult):
    """Output of `a1_validator.vat_ru()` — generic {result: ...} wrapper."""

    result: Any | None = None


class SettingsStoreResult(_BaseResult):
    """Output of `a1_validator.settings_store()` — generic {result: ...} wrapper."""

    result: Any | None = None


class ModelCatalogResult(_BaseResult):
    """Output of `a1_validator.model_catalog()`."""

    online: bool | None = None
    reason: str | None = None
    source: str | None = None
    modelsCount: int | None = None
    lastRequestUrl: str | None = None
    lastRequestMethod: str | None = None
    lastRequestHeaders: dict[str, Any] | None = None


class SupplementalSourcesResult(_BaseResult):
    """Output of `a1_validator.supplemental_sources()`."""

    count: int | None = None
    titles: list[str] | None = None
    excerpts: list[str] | None = None
    sourceUrls: list[str] | None = None
    scores: list[float] | None = None
    allAdvisory: bool | None = None


class OpenNotebookResult(_BaseResult):
    """Output of `a1_validator.open_notebook()` — multi-op, multi-shape."""

    enabled: bool | None = None
    count: int | None = None
    titles: list[str] | None = None
    texts: list[str] | None = None
    scores: list[float] | None = None
    origins: list[str] | None = None
    results: list[Any] | None = None
    lastRequestUrl: str | None = None
    lastRequestMethod: str | None = None
    lastRequestHeaders: dict[str, Any] | None = None
    lastRequestBody: Any | None = None


class ProductResearchResult(_BaseResult):
    """Output of `a1_validator.product_research()` — multi-op."""

    result: Any | None = None
    error: str | None = None
    defaultResultColumns: list[str] | None = None
    statuses: list[str] | None = None
    directions: list[str] | None = None


class InvoiceResult(_BaseResult):
    """Output of `a1_validator.invoice()` — invoice field extractor."""

    vendor_name: str | None = None
    invoice_date: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    tax_id: str | None = None


# ---------------------------------------------------------------------------
# 10 international business ID validators (added in v0.3.0).
# Each follows the { ok, normalized, error } contract from the upstream
# autoresearch-sboss example — minimal typed shape with `extra="allow"`.
# ---------------------------------------------------------------------------


class EuVatResult(_BaseResult):
    """Output of `a1_validator.eu_vat()` — EU VATIN (28 EU + GB/NO/CH)."""

    ok: bool | None = None
    normalized: str | None = None
    country: str | None = None
    error: str | None = None


class CnpjResult(_BaseResult):
    """Output of `a1_validator.cnpj()` — Brazilian CNPJ (Receita Federal)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class CpfResult(_BaseResult):
    """Output of `a1_validator.cpf()` — Brazilian CPF (Receita Federal)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class UkCompanyResult(_BaseResult):
    """Output of `a1_validator.uk_company()` — UK Company Number (Companies House)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class UsEinResult(_BaseResult):
    """Output of `a1_validator.us_ein()` — US EIN (IRS)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class GstinResult(_BaseResult):
    """Output of `a1_validator.gstin()` — India GSTIN."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class SwissUidResult(_BaseResult):
    """Output of `a1_validator.swiss_uid()` — Swiss UID (Unternehmens-Identifikationsnummer)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class AuAbnResult(_BaseResult):
    """Output of `a1_validator.au_abn()` — Australian Business Number (ATO)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class MxRfcResult(_BaseResult):
    """Output of `a1_validator.mx_rfc()` — Mexico RFC (SAT)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class JpMynumberResult(_BaseResult):
    """Output of `a1_validator.jp_mynumber()` — Japan My Number (個人番号)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# 4 more international business ID validators (added in v0.4.0).
# ---------------------------------------------------------------------------


class ArCuitResult(_BaseResult):
    """Output of `a1_validator.ar_cuit()` — Argentina CUIT/CUIL (AFIP)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class ClRutResult(_BaseResult):
    """Output of `a1_validator.cl_rut()` — Chile RUT (SII)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class SgUenResult(_BaseResult):
    """Output of `a1_validator.sg_uen()` — Singapore UEN (ACRA)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


class KrBrnResult(_BaseResult):
    """Output of `a1_validator.kr_brn()` — Korea Business Registration Number (NTS)."""

    ok: bool | None = None
    normalized: str | None = None
    error: str | None = None


# Mapping: public validator name -> Pydantic result model.
# Used by `a1_validator.validate(kind, value)` to coerce the dict result into
# the matching typed model.
RESULT_MODELS: dict[str, type[_BaseResult]] = {
    "hhvh":                 HHVHResult,
    "inn":                  INNResult,
    "model_policy":         ModelPolicyResult,
    "vat_return":           VatReturnResult,
    "payroll_am":           PayrollAmResult,
    "chart_of_accounts_am": ChartOfAccountsAmResult,
    "vat_return_form":      VatReturnFormResult,
    "phone_am":             PhoneAmResult,
    "regions_am":           RegionsAmResult,
    "einvoice_am":          EInvoiceAmResult,
    "chat_client":          ChatClientResult,
    "phone_ru":             PhoneRuResult,
    "ru_einvoice":          RuEInvoiceResult,
    "payroll_ru":           PayrollRuResult,
    "regions_ru":           RegionsRuResult,
    "chart_of_accounts_ru": ChartOfAccountsRuResult,
    "vat_ru":               VatRuResult,
    "settings_store":       SettingsStoreResult,
    "model_catalog":        ModelCatalogResult,
    "supplemental_sources": SupplementalSourcesResult,
    "open_notebook":        OpenNotebookResult,
    "product_research":     ProductResearchResult,
    "invoice":              InvoiceResult,
    # 10 international business ID validators (v0.3.0)
    "eu_vat":               EuVatResult,
    "cnpj":                 CnpjResult,
    "cpf":                  CpfResult,
    "uk_company":           UkCompanyResult,
    "us_ein":               UsEinResult,
    "gstin":                GstinResult,
    "swiss_uid":            SwissUidResult,
    "au_abn":               AuAbnResult,
    "mx_rfc":               MxRfcResult,
    "jp_mynumber":          JpMynumberResult,
    # 4 more international business ID validators (v0.4.0)
    "ar_cuit":              ArCuitResult,
    "cl_rut":               ClRutResult,
    "sg_uen":               SgUenResult,
    "kr_brn":               KrBrnResult,
}


__all__ = [
    "_BaseResult",
    "HHVHResult",
    "INNResult",
    "ModelPolicyResult",
    "VatReturnResult",
    "PayrollAmResult",
    "ChartOfAccountsAmResult",
    "VatReturnFormResult",
    "PhoneAmResult",
    "RegionsAmResult",
    "EInvoiceAmResult",
    "ChatClientResult",
    "PhoneRuResult",
    "RuEInvoiceResult",
    "PayrollRuResult",
    "RegionsRuResult",
    "ChartOfAccountsRuResult",
    "VatRuResult",
    "SettingsStoreResult",
    "ModelCatalogResult",
    "SupplementalSourcesResult",
    "OpenNotebookResult",
    "ProductResearchResult",
    "InvoiceResult",
    "EuVatResult",
    "CnpjResult",
    "CpfResult",
    "UkCompanyResult",
    "UsEinResult",
    "GstinResult",
    "SwissUidResult",
    "AuAbnResult",
    "MxRfcResult",
    "JpMynumberResult",
    "ArCuitResult",
    "ClRutResult",
    "SgUenResult",
    "KrBrnResult",
    "RESULT_MODELS",
]
