---
id: "gpt-api-phase21-22-doc-test-case-sensitive-20260615"
status: "resolved"
severity: "medium"
area: "environment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified documentation verification tests pass."
---

# Maintainer Ticket: Phase 21/22 documentation test was case-sensitive

## Issue
Targeted validation failed after adding the Phase 21/22 runbook because `tests/test_phase21_phase22_documentation_verification.py` searched for the exact lowercase phrase `canonical service URLs`, while the document heading uses `Canonical service URLs`.

## Command

```bash
pytest -q tests/test_phase16_focused_contracts.py tests/test_phase21_phase22_documentation_verification.py tests/test_phase15_release_gate.py
```

## Failure

```text
AssertionError: assert 'canonical service URLs' in '# Phase 21-22 Documentation and Verification...'
```

## Fix
Make the documentation contract test case-insensitive for phrase checks.
