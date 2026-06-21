# program.md — port a SBOSS validator into A1-Validator

You are an autonomous porting agent. Your job: **port one SBOSS workflow from
`armosphera/autoresearch-sboss/examples/<name>/` into A1-Validator's package as a
callable validator.**

This is a **port** task, not a **build** task. The source of truth exists upstream in
`autoresearch-sboss`. You do not invent validator logic — you translate it from
upstream into A1-Validator's pydantic-v2 + dict-result convention.

## The task

Given a source workflow directory like `autoresearch-sboss/examples/hhvh/`, produce a
new `a1_validator.<name>` callable in A1-Validator that:

1. Accepts a dict input matching the upstream `WORKFLOW_CONFIG["input_schema"]`.
2. Returns a dict with the upstream `WORKFLOW_CONFIG["output_schema"]` shape.
3. Surfaces errors via `{"ok": False, "error": "<message>"}` — never raises.
4. Has a corresponding pydantic v2 result model `<Name>Result` in
   `src/a1_validator/results.py`.

## The loop

```
1. Pick a candidate: see .orchestration/validator-port-queue.md
2. Read upstream: armosphera/autoresearch-sboss/examples/<name>/workflow.py
3. Read existing: src/a1_validator/_vendored/<other>.py for the convention
4. Add src/a1_validator/_vendored/<name>.py following that convention
5. Add pydantic model <Name>Result to src/a1_validator/results.py
6. Re-export from src/a1_validator/__init__.py (also add to validate() dispatcher)
7. Add tests in tests/test_validators.py covering real fixture data
8. Run pytest --cov=a1_validator --cov-fail-under=80
9. If green: commit + touch .orchestration/port-<N>-done
10. Update README.md module table + CHANGELOG.md
11. Pick next from queue, repeat
```

## Files you'll touch

| File | Why |
|---|---|
| `src/a1_validator/_vendored/<name>.py` | The ported validator body |
| `src/a1_validator/results.py` | Pydantic v2 result model |
| `src/a1_validator/__init__.py` | Re-export + `validate()` dispatcher entry |
| `tests/test_validators.py` | Tests with real fixtures |
| `README.md` | Module table |
| `CHANGELOG.md` | New entry under "Added" |
| `.orchestration/port-<N>-done` | Barrier file (touch when shipped) |

## Files you must NOT touch

- `tests/_eval_sets/` — fixed ground-truth corpus, never edit.
- `pyproject.toml` `[project]` section — version bumps are operator-driven.
- `src/a1_validator/_vendored/` files for already-ported validators — use
  `scripts/_vendor.py` to refresh from upstream if needed.

## Rules of engagement

- **DO NOT hand-translate logic.** Use `scripts/_vendor.py` if it covers the upstream
  pattern. Hand-translation only when the upstream format is unrepresentable.
- **Always use real fixtures** — public-record numbers (ИНН, ОГРН, ՀՎՀհ). Never
  synthetic.
- **Match upstream's error semantics.** If upstream raises ValueError for "too short",
  return `{"ok": False, "error": "too_short"}` not a different shape.
- **One validator per commit.** Don't bundle 5 ports into one.
- **Coverage stays ≥80%.** Pre-commit + CI gate.

## Environment

- Python 3.10–3.12 (CI matrix).
- `uv sync` to install.
- `pytest --cov=a1_validator --cov-fail-under=80` to test + enforce coverage.
- No network access required — vendoring is local file copy.

## When to stop

- **All upstream validators ported:** `.orchestration/port-<N>-done` for every N.
  Write a one-paragraph summary in `CHANGELOG.md` and declare victory.
- **A specific validator is unportable:** open an issue with the upstream path and
  why it doesn't fit the convention. Do not invent a parallel convention.
- **Coverage drops below 80%:** the diff is too big. Split it into 2-3 commits.

## Logging

Use conventional commits with `feat(validator): port <name> from autoresearch-sboss`.

Each commit body should reference the upstream source:

```
Ported from armosphera/autoresearch-sboss@<sha>:examples/<name>/workflow.py
Input/output schema matches upstream WORKFLOW_CONFIG.
```

## Coordination

- **Upstream changes:** if `armosphera/autoresearch-sboss` updates a workflow you've
  already ported, re-vendor via `scripts/_vendor.py`. Never hand-rebase.
- **Consumer asks for new field:** add to upstream first, then re-vendor into
  A1-Validator. Don't diverge.

---

*Companion to `AGENTS.md`. Together they cover the rules (AGENTS.md) and the
day-to-day loop (this file) for the validator-porting agent task.*