---
id: gpt-api-phase21-22-doc-test-case-sensitive-20260615
status: open
severity: low
area: maintenance
created: 2026-06-15
resolved:
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
