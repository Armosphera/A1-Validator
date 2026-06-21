# Validator port queue

Each row is one validator to port. Mark the row `[x]` when the corresponding
`.orchestration/port-<N>-done` file exists.

| # | Upstream | Source | Status | Notes |
|---|---|---|---|---|
| 1 | `hhvh` | `autoresearch-sboss/examples/hhvh/` | [ ] | ՀՎՀհ taxpayer ID, 8 digits |
| 2 | `inn` | `autoresearch-sboss/examples/inn/` | [ ] | Russian INN/OGRN/OGRNIP/SNILS dispatcher |
| 3 | `model_policy` | `autoresearch-sboss/examples/model_policy/` | [ ] | AI model-policy resolver |
| 4 | `vat_return` | `autoresearch-sboss/examples/vat_return/` | [ ] | Armenian VAT return compute |
| 5 | `payroll_am` | `autoresearch-sboss/examples/payroll_am/` | [ ] | Armenian payroll |
| 6 | `chart_of_accounts_am` | `autoresearch-sboss/examples/chart_of_accounts_am/` | [ ] | 623-account lookup |
| 7 | `vat_return_form` | `autoresearch-sboss/examples/vat_return_form/` | [ ] | VAT return form validation |
| 8 | `phone_am` | `autoresearch-sboss/examples/phone_am/` | [ ] | Armenian phone NSN/E.164 |
| 9 | `regions_am` | `autoresearch-sboss/examples/regions_am/` | [ ] | 11 marzer lookup |
| 10 | `einvoice_am` | `autoresearch-sboss/examples/einvoice_am/` | [ ] | Armenian e-invoice structural |
| 11 | `chat_client` | `autoresearch-sboss/examples/chat_client/` | [ ] | OpenRouter chat client (mock-able) |
| 12 | `phone_ru` | `autoresearch-sboss/examples/phone_ru/` | [ ] | Russian phone NSN/E.164 |
| 13 | `ru_einvoice` | `autoresearch-sboss/examples/ru_einvoice/` | [ ] | Russian e-invoice validate + XML |
| 14 | `payroll_ru` | `autoresearch-sboss/examples/payroll_ru/` | [ ] | Russian payroll NDFL + insurance |
| 15 | `regions_ru` | `autoresearch-sboss/examples/regions_ru/` | [ ] | 83 Russian regions |
| 16 | `chart_of_accounts_ru` | `autoresearch-sboss/examples/chart_of_accounts_ru/` | [ ] | 73 Russian accounts |
| 17 | `vat_ru` | `autoresearch-sboss/examples/vat_ru/` | [ ] | Russian VAT rate helpers |
| 18 | `settings_store` | `autoresearch-sboss/examples/settings_store/` | [ ] | Local JSON settings |
| 19 | `model_catalog` | `autoresearch-sboss/examples/model_catalog/` | [ ] | OpenRouter model catalog |
| 20 | `supplemental_sources` | `autoresearch-sboss/examples/supplemental_sources/` | [ ] | Supplemental research normalizer |
| 21 | `open_notebook` | `autoresearch-sboss/examples/open_notebook/` | [ ] | Notebook search/enable |
| 22 | `product_research` | `autoresearch-sboss/examples/product_research/` | [ ] | Product-research program |
| 23 | `invoice` | `autoresearch-sboss/examples/invoice/` | [ ] | Invoice field extractor |

## Workflow

For each row:

```
1. Read .orchestration/program.md (the agent charter)
2. Read upstream: armosphera/autoresearch-sboss/examples/<name>/
3. Implement port in src/a1_validator/_vendored/<name>.py
4. Add <Name>Result to src/a1_validator/results.py
5. Re-export from src/a1_validator/__init__.py
6. Add test cases to tests/test_validators.py
7. Run pytest --cov=a1_validator --cov-fail-under=80
8. Commit with conventional prefix
9. Mark row [x] + touch .orchestration/port-<N>-done
10. Move to next row
```

## Barrier

- `.orchestration/port-<N>-done` — touched when row N ships. Created by the agent.
- When all 23 are done: write a summary in `CHANGELOG.md` and stop.