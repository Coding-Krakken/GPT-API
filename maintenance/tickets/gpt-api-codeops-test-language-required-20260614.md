---
id: "gpt-api-codeops-test-language-required-20260614"
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

# Maintainer Ticket: codeOps test endpoint requires language for pytest file

## Issue
While implementing GPT-API Phases 1-3, the structured `/code` operation endpoint was used with `action: test` against `tests/test_phase1_phase3_route_normalization.py`, but the request failed validation because `language` was required.

## Attempted request
```json
{
  "action": "test",
  "path": "tests/test_phase1_phase3_route_normalization.py",
  "working_dir": "/root/GPT-API",
  "timeout_seconds": 120,
  "max_output_bytes": 20000
}
```

## Error
```json
{"detail":[{"type":"missing","loc":["body","language"],"msg":"Field required"}]}
```

## Expected
For test actions against an existing `.py` file, the endpoint should infer Python or document that `language: python` is required.

## Workaround
Use `/shell` to run `pytest` directly or include `language: python` in the structured call.


## Phase 2 resolution

Implemented and verified in Phase 2. `/code` test mode now supports inferred Python language for pytest files and repo roots, repository-root pytest execution, safe multi-file pytest selectors through `argv` or `args`, `PYTHONPATH` injection from `working_dir`, and structured `validationResult` metadata for test runs.
