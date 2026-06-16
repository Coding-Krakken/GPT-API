# Maintainer Ticket Remediation Report

Generated as Phase 1 of the maintainer ticket lifecycle cleanup.

## Current classification

The maintainer ticket backlog has been normalized into explicit lifecycle states:

- `open` — still actionable and should be implemented or investigated.
- `needs_verification` — likely environment/deployment dependent; requires a fresh verification run.
- `resolved` — verified fixed on current `main`.
- `obsolete` — one-off implementation/tooling incident no longer tracked as an active defect.
- `duplicate` — reserved for future duplicate consolidation.

## Active remediation themes

### P0 — codeOps test-mode robustness

Affected tickets:

- `gpt-api-codeops-pytest-import-path-20260614`
- `gpt-api-codeops-test-language-required-20260614`
- `gpt-api-phase14-17-codeops-language-required-20260614`
- `gpt-api-phase18-20-codeops-multipath-test-20260615`
- `gpt-api-phase21-22-codeops-pytest-args-rejected-20260615`

Required work:

- Infer language for test actions when safe.
- Support repo-root pytest runs.
- Support multi-file pytest selectors through `argv`.
- Set `PYTHONPATH` to `working_dir` for Python repo tests.
- Return structured validation results aligned with `/test/run`.

### P0 — live deployment and GPT Action drift

Affected tickets include live ngrok, production port 8000, and stale-service reports.

Required work:

- Add a deployment verification script.
- Verify running process commit equals `origin/main`.
- Verify localhost and ngrok health/schema endpoints.
- Verify Coding GPT Action schemas are re-imported from the correct files.

### P1 — environment/bootstrap consistency

Affected tickets:

- `gpt-api-tests-missing-requests-dependency-20260614`
- `gpt-api-broad-tests-missing-requests-20260615`
- `gpt-api-implementation-issues-20260608`

Required work:

- Add canonical bootstrap/check-env scripts.
- Verify active interpreter dependencies match `requirements.txt`.
- Document the supported venv/interpreter.

### P1 — patch/file safety hardening

Affected tickets:

- `gpt-api-main-patch-literal-corruption-20260614`
- `gpt-api-phase11-13-patch-endpoint-corruption-20260614`

Required work:

- Add malformed patch regression tests.
- Add literal patch corruption regression tests.
- Verify preview/apply safety parity.

### P1 — encoding and output robustness

Affected tickets include response-too-large, decode, and non-UTF8 file inspection failures.

Required work:

- Add bounded log readers.
- Add binary/non-UTF8-safe inspection helpers.
- Add tests for output truncation and decoding behavior.

## Verification baseline used for resolved tickets

Resolved tickets were marked using this local verification baseline where applicable:

```bash
python3 scripts/validate_openapi.py
./scripts/release_gate.sh
python3 scripts/smoke_local.py
pytest -q
```

## Next phase

Phase 2 should implement codeOps test-mode robustness because it has the highest concentration of still-actionable endpoint tickets.
