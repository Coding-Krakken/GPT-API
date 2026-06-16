---
id: "gpt-api-phase21-22-codeops-pytest-args-rejected-20260615"
status: "resolved"
severity: "high"
area: "codeops"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "8dd867b"
verification_command: "pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py"
verification_result: "50 passed, 1 warning"
resolution_summary: "Phase 2 implemented robust /code test mode: language inference, repo-root pytest, working_dir PYTHONPATH, multi-file argv/selectors, and validationResult output."
---

# Maintainer Ticket: codeOps rejected targeted pytest arguments during Phase 21/22 validation

## Issue
While validating Phase 21/22 changes in `/root/GPT-API`, the structured `/code` test endpoint rejected a targeted pytest argument string.

## Attempted request

```text
action=test
language=python
path=/root/GPT-API
args=-q tests/test_phase16_focused_contracts.py tests/test_phase21_phase22_documentation_verification.py tests/test_phase15_release_gate.py
```

## Error

```json
{"error":{"code":"invalid_args","message":"Unsupported, malformed, or unsafe arguments."},"status":400}
```

## Workaround
Run the same targeted pytest selection through a bounded shell command.


## Phase 2 resolution

Implemented and verified in Phase 2. `/code` test mode now supports inferred Python language for pytest files and repo roots, repository-root pytest execution, safe multi-file pytest selectors through `argv` or `args`, `PYTHONPATH` injection from `working_dir`, and structured `validationResult` metadata for test runs.
