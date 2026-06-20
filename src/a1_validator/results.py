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

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class _BaseResult(BaseModel):
    """Common config: allow extras, suppress unknown-field warnings."""

    model_config = ConfigDict(extra="allow", frozen=False)


# ---------------------------------------------------------------------------
# 23 result models — one per validator.
# ---------------------------------------------------------------------------


class HHVHResult(_BaseResult):
    """Output of `a1_validator.hhvh()`."""

    ok: Optional[bool] = None
    normalized: Optional[str] = None
    error: Optional[str] = None


class INNResult(_BaseResult):
    """Output of `a1_validator.inn()` — Russian identifier dispatcher."""

    ok: Optional[bool] = None
    normalized: Optional[str] = None
    kind: Optional[str] = None
    error: Optional[str] = None


class ModelPolicyResult(_BaseResult):
    """Output of `a1_validator.model_policy()`."""

    resolved_model: Optional[str] = None
    source: Optional[str] = None


class VatReturnResult(_BaseResult):
    """Output of `a1_validator.vat_return()`."""

    net: Optional[float] = None
    outputVat: Optional[float] = None
    inputVat: Optional[float] = None
    payable: Optional[float] = None
    creditCarried: Optional[float] = None
    taxableSales: Optional[float] = None
    taxablePurchases: Optional[float] = None


class PayrollAmResult(_BaseResult):
    """Output of `a1_validator.payroll_am()`."""

    gross: Optional[float] = None
    incomeTax: Optional[float] = None
    pension: Optional[float] = None
    healthInsurance: Optional[float] = None
    stampDuty: Optional[float] = None
    totalWithholdings: Optional[float] = None
    net: Optional[float] = None


class ChartOfAccountsAmResult(_BaseResult):
    """Output of `a1_validator.chart_of_accounts_am()`."""

    code: Optional[Any] = None
    ok: Optional[bool] = None
    normalized: Optional[str] = None
    hy: Optional[str] = None
    class_: Optional[int] = None  # `class` is a Python keyword — use the alias.
    type: Optional[str] = None
    error: Optional[str] = None

    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        # Map incoming `class` key to `class_` field.
        if isinstance(obj, dict) and "class" in obj and "class_" not in obj:
            obj = {**obj, "class_": obj["class"]}
        return super().model_validate(obj, *args, **kwargs)


class VatReturnFormResult(_BaseResult):
    """Output of `a1_validator.vat_return_form()`."""

    ok: Optional[bool] = None
    error_count: Optional[int] = None
    error_codes: Optional[list[str]] = None


class PhoneAmResult(_BaseResult):
    """Output of `a1_validator.phone_am()`."""

    nsn: Optional[str] = None
    valid: Optional[bool] = None
    e164: Optional[str] = None
    formatted: Optional[str] = None


class RegionsAmResult(_BaseResult):
    """Output of `a1_validator.regions_am()`."""

    found: Optional[bool] = None
    code: Optional[str] = None
    hy: Optional[str] = None
    en: Optional[str] = None
    center: Optional[str] = None


class EInvoiceAmResult(_BaseResult):
    """Output of `a1_validator.einvoice_am()`."""

    ok: Optional[bool] = None
    error_count: Optional[int] = None
    error_codes: Optional[list[str]] = None


class ChatClientResult(_BaseResult):
    """Output of `a1_validator.chat_client()`."""

    ok: Optional[bool] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    text: Optional[str] = None
    responseId: Optional[str] = None
    error_code: Optional[str] = None
    error_status: Optional[int] = None
    last_request: Optional[dict[str, Any]] = None


class PhoneRuResult(_BaseResult):
    """Output of `a1_validator.phone_ru()`."""

    nsn: Optional[str] = None
    valid: Optional[bool] = None
    e164: Optional[str] = None
    formatted: Optional[str] = None


class RuEInvoiceResult(_BaseResult):
    """Output of `a1_validator.ru_einvoice()`."""

    ok: Optional[bool] = None
    error_count: Optional[int] = None
    error_codes: Optional[list[str]] = None


class PayrollRuResult(_BaseResult):
    """Output of `a1_validator.payroll_ru()` — generic {result: ...} wrapper."""

    result: Optional[Any] = None


class RegionsRuResult(_BaseResult):
    """Output of `a1_validator.regions_ru()`."""

    found: Optional[bool] = None
    code: Optional[str] = None
    ru: Optional[str] = None
    en: Optional[str] = None
    center: Optional[str] = None


class ChartOfAccountsRuResult(_BaseResult):
    """Output of `a1_validator.chart_of_accounts_ru()`."""

    found: Optional[bool] = None
    code: Optional[str] = None
    ru: Optional[str] = None
    section: Optional[str] = None
    nature: Optional[str] = None
    normalBalance: Optional[str] = None


class VatRuResult(_BaseResult):
    """Output of `a1_validator.vat_ru()` — generic {result: ...} wrapper."""

    result: Optional[Any] = None


class SettingsStoreResult(_BaseResult):
    """Output of `a1_validator.settings_store()` — generic {result: ...} wrapper."""

    result: Optional[Any] = None


class ModelCatalogResult(_BaseResult):
    """Output of `a1_validator.model_catalog()`."""

    online: Optional[bool] = None
    reason: Optional[str] = None
    source: Optional[str] = None
    modelsCount: Optional[int] = None
    lastRequestUrl: Optional[str] = None
    lastRequestMethod: Optional[str] = None
    lastRequestHeaders: Optional[dict[str, Any]] = None


class SupplementalSourcesResult(_BaseResult):
    """Output of `a1_validator.supplemental_sources()`."""

    count: Optional[int] = None
    titles: Optional[list[str]] = None
    excerpts: Optional[list[str]] = None
    sourceUrls: Optional[list[str]] = None
    scores: Optional[list[float]] = None
    allAdvisory: Optional[bool] = None


class OpenNotebookResult(_BaseResult):
    """Output of `a1_validator.open_notebook()` — multi-op, multi-shape."""

    enabled: Optional[bool] = None
    count: Optional[int] = None
    titles: Optional[list[str]] = None
    texts: Optional[list[str]] = None
    scores: Optional[list[float]] = None
    origins: Optional[list[str]] = None
    results: Optional[list[Any]] = None
    lastRequestUrl: Optional[str] = None
    lastRequestMethod: Optional[str] = None
    lastRequestHeaders: Optional[dict[str, Any]] = None
    lastRequestBody: Optional[Any] = None


class ProductResearchResult(_BaseResult):
    """Output of `a1_validator.product_research()` — multi-op."""

    result: Optional[Any] = None
    error: Optional[str] = None
    defaultResultColumns: Optional[list[str]] = None
    statuses: Optional[list[str]] = None
    directions: Optional[list[str]] = None


class InvoiceResult(_BaseResult):
    """Output of `a1_validator.invoice()` — invoice field extractor."""

    vendor_name: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    tax_id: Optional[str] = None


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
    "RESULT_MODELS",
]