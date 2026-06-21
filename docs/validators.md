# Validators

Auto-generated reference for every public validator in `a1_validator`. The table below covers all 23 kinds in their canonical order; per-kind sections below show a real example input (lifted from the vendored `tests/_eval_sets/<kind>.json` corpus) and the actual dict returned by the installed library — re-run `python scripts/gen_validators_md.py` after editing the package to refresh this page.

## Summary

| # | Kind | Description | Input shape |
| - | ---- | ----------- | ----------- |
| 1 | `hhvh` | Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ) | `error, normalized, ok` |
| 2 | `inn` | Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (`ru-identifiers`) | `error, kind, normalized, ok` |
| 3 | `model_policy` | AI model-policy resolver (module → model) | `resolved_model, source` |
| 4 | `vat_return` | Armenian VAT return compute (sales/purchases → owed) | `creditCarried, inputVat, net, outputVat, payable, taxablePurchases, taxableSales` |
| 5 | `payroll_am` | Armenian payroll compute (gross → taxes/net) | `gross, healthInsurance, incomeTax, net, pension, stampDuty, totalWithholdings` |
| 6 | `chart_of_accounts_am` | Armenian chart-of-accounts lookup + validate (623 accounts) | `class_, code, error, hy, normalized, ok, type` |
| 7 | `vat_return_form` | Armenian VAT-return form validation (line codes + amounts) | `error_codes, error_count, ok` |
| 8 | `phone_am` | Armenian phone NSN/E.164/format | `e164, formatted, nsn, valid` |
| 9 | `regions_am` | Armenian regions lookup (name/en/code → center) | `center, code, en, found, hy` |
| 10 | `einvoice_am` | Armenian e-invoice structural validation | `error_codes, error_count, ok` |
| 11 | `chat_client` | OpenRouter chat client (mock-able HTTP transport) | `error_code, error_status, last_request, model, ok, provider, responseId, text` |
| 12 | `phone_ru` | Russian phone NSN/E.164/format | `e164, formatted, nsn, valid` |
| 13 | `ru_einvoice` | Russian e-invoice validate + XML build | `error_codes, error_count, ok` |
| 14 | `payroll_ru` | Russian payroll (NDFL, insurance, monthly ops) | `result` |
| 15 | `regions_ru` | Russian regions lookup (83 entries) | `center, code, en, found, ru` |
| 16 | `chart_of_accounts_ru` | Russian chart-of-accounts lookup (73 accounts, 9 sections) | `code, found, nature, normalBalance, ru, section` |
| 17 | `vat_ru` | Russian VAT rate helpers + valid-rate check | `result` |
| 18 | `settings_store` | Local JSON settings store (read/write/list/delete) | `result` |
| 19 | `model_catalog` | OpenRouter model catalog fetch + normalize | `lastRequestHeaders, lastRequestMethod, lastRequestUrl, modelsCount, online, reason, source` |
| 20 | `supplemental_sources` | Supplemental research sources normalizer | `allAdvisory, count, excerpts, scores, sourceUrls, titles` |
| 21 | `open_notebook` | Notebook search/enable/normalize ops | `count, enabled, lastRequestBody, lastRequestHeaders, lastRequestMethod, lastRequestUrl, origins, results, scores, texts, titles` |
| 22 | `product_research` | Product-research config + program render + decide | `defaultResultColumns, directions, error, result, statuses` |
| 23 | `invoice` | Invoice field extractor (regex/mock, deterministic) | `currency, invoice_date, tax_id, total_amount, vendor_name` |
| 24 | `eu_vat` | EU VATIN (VAT identification number, 28 EU + GB/NO/CH) | `country, error, normalized, ok` |
| 25 | `cnpj` | Brazilian CNPJ (14 digits, mod-11 DV per Receita Federal) | `error, normalized, ok` |
| 26 | `cpf` | Brazilian CPF (11 digits, mod-11 DV per Receita Federal) | `error, normalized, ok` |
| 27 | `uk_company` | UK Company Number (8 digits, or SC/NI/OC/SO + 6 digits) | `error, normalized, ok` |
| 28 | `us_ein` | US EIN (9 digits, IRS campus code prefix) | `error, normalized, ok` |
| 29 | `gstin` | India GSTIN (15 alphanumeric, state code + PAN + Z + check) | `error, normalized, ok` |
| 30 | `swiss_uid` | Swiss UID (CHE/CH/CDF + 9 digits) | `error, normalized, ok` |
| 31 | `au_abn` | Australian Business Number (11 digits, mod-89 check) | `error, normalized, ok` |
| 32 | `mx_rfc` | Mexico RFC (12-13 chars, SAT mod-11 verification digit) | `error, normalized, ok` |
| 33 | `jp_mynumber` | Japan My Number (12 digits, mod-11 check, 個人番号) | `error, normalized, ok` |

## Per-kind reference

### 1. `hhvh`

**Armenian taxpayer ID (8 digits, HHVH / ՀՎՀՀ)**

- **Aliases**: —
- **Example source**: `hhvh.json`
- **Pydantic result model**: `a1_validator.HHVHResult`

**Example input**

```json
{
  "hvhh": "00123456"
}
```

**Example output**

```json
{
  "error": null,
  "normalized": "00123456",
  "ok": true
}
```

### 2. `inn`

**Russian INN / OGRN / OGRNIP / SNILS / KPP dispatcher (`ru-identifiers`)**

- **Aliases**: identifier, ru_identifiers
- **Example source**: `inn.json`
- **Pydantic result model**: `a1_validator.INNResult`

**Example input**

```json
{
  "id": "7707083893"
}
```

**Example output**

```json
{
  "error": null,
  "kind": "inn_legal",
  "normalized": "7707083893",
  "ok": true
}
```

### 3. `model_policy`

**AI model-policy resolver (module → model)**

- **Aliases**: —
- **Example source**: `model_policy.json`
- **Pydantic result model**: `a1_validator.ModelPolicyResult`

**Example input**

```json
{
  "ctx": {},
  "policy": {
    "default": "anthropic/claude-3.5-sonnet"
  }
}
```

**Example output**

```json
{
  "resolved_model": "anthropic/claude-3.5-sonnet",
  "source": "default"
}
```

### 4. `vat_return`

**Armenian VAT return compute (sales/purchases → owed)**

- **Aliases**: —
- **Example source**: `vat_return.json`
- **Pydantic result model**: `a1_validator.VatReturnResult`

**Example input**

```json
{
  "purchases": [
    {
      "netAmount": 400000,
      "vatRate": 20
    }
  ],
  "sales": [
    {
      "netAmount": 1000000,
      "vatRate": 20
    }
  ]
}
```

**Example output**

```json
{
  "creditCarried": 0,
  "inputVat": 80000,
  "net": 120000,
  "outputVat": 200000,
  "payable": 120000,
  "taxablePurchases": 400000,
  "taxableSales": 1000000
}
```

### 5. `payroll_am`

**Armenian payroll compute (gross → taxes/net)**

- **Aliases**: —
- **Example source**: `payroll_am.json`
- **Pydantic result model**: `a1_validator.PayrollAmResult`

**Example input**

```json
{
  "gross": 0
}
```

**Example output**

```json
{
  "gross": 0,
  "healthInsurance": 0,
  "incomeTax": 0,
  "net": 0,
  "pension": 0,
  "stampDuty": 0,
  "totalWithholdings": 0
}
```

### 6. `chart_of_accounts_am`

**Armenian chart-of-accounts lookup + validate (623 accounts)**

- **Aliases**: —
- **Example source**: `chart_of_accounts_am.json`
- **Pydantic result model**: `a1_validator.ChartOfAccountsAmResult`

**Example input**

```json
{
  "code": "111"
}
```

**Example output**

```json
{
  "class": 1,
  "code": "111",
  "error": null,
  "hy": "Մաշվող հիմնական միջոցներ",
  "normalized": "111",
  "ok": true,
  "type": "asset"
}
```

### 7. `vat_return_form`

**Armenian VAT-return form validation (line codes + amounts)**

- **Aliases**: —
- **Example source**: `vat_return_form.json`
- **Pydantic result model**: `a1_validator.VatReturnFormResult`

**Example input**

```json
{
  "form": {
    "lines": {
      "12": {
        "base": 200000
      },
      "13": {
        "base": 50000
      },
      "16": {
        "base": 1850000,
        "vat": 300020
      },
      "17": {
        "base": 300000,
        "vat": 60000
      },
      "18": {
        "base": 400000,
        "vat": 80000
      },
      "21": {
        "vat": 140000
      },
      "23": {
        "payable": 160020,
        "recoverable": 0
      },
      "7": {
        "base": 1000000,
        "vat": 200000
      },
      "9": {
        "base": 600000,
        "vat": 100020
      }
    }
  }
}
```

**Example output**

```json
{
  "error_codes": [],
  "error_count": 0,
  "ok": true
}
```

### 8. `phone_am`

**Armenian phone NSN/E.164/format**

- **Aliases**: —
- **Example source**: `phone_am.json`
- **Pydantic result model**: `a1_validator.PhoneAmResult`

**Example input**

```json
{
  "phone": "+37491234567"
}
```

**Example output**

```json
{
  "e164": "+37491234567",
  "formatted": "+374 91 234567",
  "nsn": "91234567",
  "valid": true
}
```

### 9. `regions_am`

**Armenian regions lookup (name/en/code → center)**

- **Aliases**: —
- **Example source**: `regions_am.json`
- **Pydantic result model**: `a1_validator.RegionsAmResult`

**Example input**

```json
{
  "query": "AM-ER"
}
```

**Example output**

```json
{
  "center": "Երևան",
  "code": "AM-ER",
  "en": "Yerevan",
  "found": true,
  "hy": "Երևան"
}
```

### 10. `einvoice_am`

**Armenian e-invoice structural validation**

- **Aliases**: —
- **Example source**: `einvoice_am.json`
- **Pydantic result model**: `a1_validator.EInvoiceAmResult`

**Example input**

```json
{
  "invoice": {
    "buyer": {
      "hvhh": "11111112",
      "name": "Buyer Inc"
    },
    "issueDate": "2025-03-15",
    "lines": [
      {
        "description": "Service A",
        "netAmount": 100000,
        "quantity": 2,
        "vatRate": 20
      },
      {
        "description": "Service B",
        "netAmount": 50000,
        "quantity": 1,
        "vatRate": 20
      },
      {
        "description": "Service C",
        "netAmount": 25000,
        "quantity": 1,
        "vatRate": 20
      }
    ],
    "number": "INV-001",
    "supplier": {
      "hvhh": "01234567",
      "name": "ACME Corp"
    },
    "transactionType": "SALE"
  }
}
```

**Example output**

```json
{
  "error_codes": [],
  "error_count": 0,
  "ok": true
}
```

### 11. `chat_client`

**OpenRouter chat client (mock-able HTTP transport)**

- **Aliases**: —
- **Example source**: `chat_client.json`
- **Pydantic result model**: `a1_validator.ChatClientResult`

**Example input**

```json
{
  "kwargs": {
    "apiKey": "sk-test-123",
    "input": "Hi",
    "instructions": "You are helpful."
  },
  "openrouter": {
    "baseUrl": "https://openrouter.ai/api/v1"
  },
  "operation": "callModel",
  "safeFetch_ok": true,
  "safeFetch_response": {
    "choices": [
      {
        "message": {
          "content": "Hello there.",
          "role": "assistant"
        }
      }
    ],
    "id": "chatcmpl-test-001",
    "model": "anthropic/claude-3.5-sonnet",
    "usage": {
      "completion_tokens": 3,
      "prompt_tokens": 10,
      "total_tokens": 13
    }
  },
  "safeFetch_status": 200
}
```

**Example output**

```json
{
  "endpoint": "https://openrouter.ai/api/v1/chat/completions",
  "last_request": {
    "body": {
      "max_tokens": 1200,
      "messages": [
        {
          "content": "You are helpful.",
          "role": "system"
        },
        {
          "content": "Hi",
          "role": "user"
        }
      ]
    },
    "headers": {
      "Authorization": "Bearer sk-test-123",
      "Content-Type": "application/json",
      "HTTP-Referer": "",
      "X-Title": ""
    },
    "method": "POST",
    "url": "https://openrouter.ai/api/v1/chat/completions"
  },
  "model": "anthropic/claude-3.5-sonnet",
  "ok": true,
  "operation": "callModel",
  "provider": "openrouter",
  "responseId": "chatcmpl-test-001",
  "text": "Hello there.",
  "usage": {
    "completion_tokens": 3,
    "prompt_tokens": 10,
    "total_tokens": 13
  }
}
```

### 12. `phone_ru`

**Russian phone NSN/E.164/format**

- **Aliases**: —
- **Example source**: `phone_ru.json`
- **Pydantic result model**: `a1_validator.PhoneRuResult`

**Example input**

```json
{
  "value": "+7 (495) 123-45-67"
}
```

**Example output**

```json
{
  "e164": "+74951234567",
  "formatted": "+7 (495) 123-45-67",
  "nsn": "4951234567",
  "valid": true
}
```

### 13. `ru_einvoice`

**Russian e-invoice validate + XML build**

- **Aliases**: —
- **Example source**: `ru_einvoice.json`
- **Pydantic result model**: `a1_validator.RuEInvoiceResult`

**Example input**

```json
{
  "invoice": {
    "buyer": {
      "address": "SPb",
      "inn": "7707083893",
      "kpp": "770701001",
      "name": "Acme LLC"
    },
    "currency": "RUB",
    "date": "2026-03-15",
    "lines": [
      {
        "description": "Service A",
        "lineTotal": 12200.0,
        "netAmount": 10000.0,
        "quantity": 2,
        "vatAmount": 2200.0,
        "vatRate": 22
      }
    ],
    "number": "SF-2026-001",
    "seller": {
      "address": "Moscow",
      "inn": "7707083893",
      "kpp": "770701001",
      "name": "Sberbank"
    }
  },
  "operation": "validate"
}
```

**Example output**

```json
{
  "error_codes": [],
  "error_count": 0,
  "ok": true
}
```

### 14. `payroll_ru`

**Russian payroll (NDFL, insurance, monthly ops)**

- **Aliases**: —
- **Example source**: `payroll_ru.json`
- **Pydantic result model**: `a1_validator.PayrollRuResult`

**Example input**

```json
{
  "base": 1000000,
  "operation": "ndflOnAnnualBase",
  "opts": {
    "resident": true
  }
}
```

**Example output**

```json
{
  "result": 130000
}
```

### 15. `regions_ru`

**Russian regions lookup (83 entries)**

- **Aliases**: —
- **Example source**: `regions_ru.json`
- **Pydantic result model**: `a1_validator.RegionsRuResult`

**Example input**

```json
{
  "query": "RU-MOW"
}
```

**Example output**

```json
{
  "center": "Москва",
  "code": "RU-MOW",
  "en": "Moscow",
  "found": true,
  "ru": "Москва"
}
```

### 16. `chart_of_accounts_ru`

**Russian chart-of-accounts lookup (73 accounts, 9 sections)**

- **Aliases**: —
- **Example source**: `chart_of_accounts_ru.json`
- **Pydantic result model**: `a1_validator.ChartOfAccountsRuResult`

**Example input**

```json
{
  "code": "01"
}
```

**Example output**

```json
{
  "code": "01",
  "found": true,
  "nature": "active",
  "normalBalance": "debit",
  "ru": "Основные средства",
  "section": "I"
}
```

### 17. `vat_ru`

**Russian VAT rate helpers + valid-rate check**

- **Aliases**: —
- **Example source**: `vat_ru.json`
- **Pydantic result model**: `a1_validator.VatRuResult`

**Example input**

```json
{
  "operation": "ratesFor",
  "year": 2026
}
```

**Example output**

```json
{
  "result": {
    "reduced": 10,
    "standard": 22,
    "usnHigh": 7,
    "usnLow": 5,
    "zero": 0
  }
}
```

### 18. `settings_store`

**Local JSON settings store (read/write/list/delete)**

- **Aliases**: —
- **Example source**: `settings_store.json`
- **Pydantic result model**: `a1_validator.SettingsStoreResult`

**Example input**

```json
{
  "operations": [
    {
      "operation": "defaults"
    }
  ]
}
```

**Example output**

```json
{
  "result": {
    "models": {
      "copilot": "",
      "crm": "",
      "default": "",
      "docs": "",
      "finance": "",
      "transform": ""
    },
    "openNotebook": {
      "apiKey": "",
      "baseUrl": "",
      "enabled": false
    },
    "openrouterApiKey": ""
  }
}
```

### 19. `model_catalog`

**OpenRouter model catalog fetch + normalize**

- **Aliases**: —
- **Example source**: `model_catalog.json`
- **Pydantic result model**: `a1_validator.ModelCatalogResult`

**Example input**

```json
{
  "egressAllowed": false,
  "openrouter": {
    "modelsUrl": "https://openrouter.ai/api/v1/models",
    "referer": "",
    "title": ""
  },
  "safeFetchResponse": {
    "data": [
      {
        "context_length": 200000,
        "id": "anthropic/claude-3.5-sonnet",
        "name": "Anthropic: Claude 3.5 Sonnet",
        "pricing": {
          "completion": "0.000015",
          "prompt": "0.000003"
        }
      },
      {
        "context_length": 128000,
        "id": "openai/gpt-4o",
        "name": "OpenAI: GPT-4o",
        "pricing": {
          "completion": "0.000015",
          "prompt": "0.000005"
        }
      }
    ]
  }
}
```

**Example output**

```json
{
  "lastRequestHeaders": null,
  "lastRequestMethod": null,
  "lastRequestUrl": null,
  "modelsCount": 5,
  "online": false,
  "reason": "egress-blocked",
  "source": "fallback"
}
```

### 20. `supplemental_sources`

**Supplemental research sources normalizer**

- **Aliases**: —
- **Example source**: `supplemental_sources.json`
- **Pydantic result model**: `a1_validator.SupplementalSourcesResult`

**Example input**

```json
{
  "raw": []
}
```

**Example output**

```json
{
  "allAdvisory": true,
  "count": 0,
  "excerpts": [],
  "scores": [],
  "sourceUrls": [],
  "titles": []
}
```

### 21. `open_notebook`

**Notebook search/enable/normalize ops**

- **Aliases**: —
- **Example source**: `open_notebook.json`
- **Pydantic result model**: `a1_validator.OpenNotebookResult`

**Example input**

```json
{
  "operation": "isEnabled",
  "settings": null
}
```

**Example output**

```json
{
  "enabled": false
}
```

### 22. `product_research`

**Product-research config + program render + decide**

- **Aliases**: —
- **Example source**: `product_research.json`
- **Pydantic result model**: `a1_validator.ProductResearchResult`

**Example input**

```json
{
  "operation": "constants"
}
```

**Example output**

```json
{
  "defaultResultColumns": [
    "commit",
    "metric",
    "memory_gb",
    "status",
    "description"
  ],
  "directions": [
    "maximize",
    "minimize"
  ],
  "statuses": [
    "crash",
    "discard",
    "keep"
  ]
}
```

### 23. `invoice`

**Invoice field extractor (regex/mock, deterministic)**

- **Aliases**: —
- **Example source**: `invoice.json`
- **Pydantic result model**: `a1_validator.InvoiceResult`

**Example input**

```json
{
  "document": "ACME Corporation LLC\n1234 Industrial Way\nSpringfield, IL 62701\n\nINVOICE\nNumber: INV-2025-0142\nDate: 2025-03-15\nDue Date: 2025-04-15\n\nDescription                          Qty    Unit Price    Amount\nProfessional Services               40     $125.00       $5,000.00\nSoftware License (Annual)            1     $2,500.00     $2,500.00\n\nSubtotal: $7,500.00\nTax (8.25%): $618.75\nTotal: $8,118.75 USD\n\nTax ID: 12-3456789\nPayable to: ACME Corporation LLC"
}
```

**Example output**

```json
{
  "currency": "USD",
  "invoice_date": "2025-03-15",
  "tax_id": "12-3456789",
  "total_amount": 8118.75,
  "vendor_name": "ACME Corporation LLC"
}
```

### 24. `eu_vat`

**EU VATIN (VAT identification number, 28 EU + GB/NO/CH)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.EuVatResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 25. `cnpj`

**Brazilian CNPJ (14 digits, mod-11 DV per Receita Federal)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.CnpjResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 26. `cpf`

**Brazilian CPF (11 digits, mod-11 DV per Receita Federal)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.CpfResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 27. `uk_company`

**UK Company Number (8 digits, or SC/NI/OC/SO + 6 digits)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.UkCompanyResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 28. `us_ein`

**US EIN (9 digits, IRS campus code prefix)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.UsEinResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 29. `gstin`

**India GSTIN (15 alphanumeric, state code + PAN + Z + check)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.GstinResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 30. `swiss_uid`

**Swiss UID (CHE/CH/CDF + 9 digits)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.SwissUidResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 31. `au_abn`

**Australian Business Number (11 digits, mod-89 check)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.AuAbnResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 32. `mx_rfc`

**Mexico RFC (12-13 chars, SAT mod-11 verification digit)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.MxRfcResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```

### 33. `jp_mynumber`

**Japan My Number (12 digits, mod-11 check, 個人番号)**

- **Aliases**: —
- **Example source**: `(no vendored eval set)`
- **Pydantic result model**: `a1_validator.JpMynumberResult`

**Example input**

```json
"<see docs>"
```

**Example output**

```json
{
  "error": "AttributeError: 'str' object has no attribute 'get'"
}
```
