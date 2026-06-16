---
id: "gpt-api-phase14-17-codeops-language-required-20260614"
status: "resolved"
severity: "high"
area: "codeops"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "4237779"
verification_command: "pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py"
verification_result: "50 passed, 1 warning"
resolution_summary: "Phase 2 implemented robust /code test mode: language inference, repo-root pytest, working_dir PYTHONPATH, multi-file argv/selectors, and validationResult output."
---

# GPT-API Phase 14-17 codeOps test language requirement

## Issue
While running the Phase 14-17 pytest suite through the structured `/code` operation endpoint, the request failed validation because `language` was required even though the action was `test` with an explicit pytest argv.

## Attempted request
```json
{
  "action": "test",
  "path": "/root/GPT-API",
  "argv": ["pytest", "-q", "tests/test_phase14_ticket_triage.py", "tests/test_phase15_release_gate.py", "tests/test_phase16_focused_contracts.py", "tests/test_phase17_error_envelope.py"],
  "timeout_seconds": 120,
  "max_output_bytes": 60000
}
```

## Error
```text
Field required: language
```

## Context
Repository: `/root/GPT-API`
Task: implement Phases 14-17, commit and push all changes.

## Workaround
Run pytest via a bounded shell command.


## Phase 2 resolution

Implemented and verified in Phase 2. `/code` test mode now supports inferred Python language for pytest files and repo roots, repository-root pytest execution, safe multi-file pytest selectors through `argv` or `args`, `PYTHONPATH` injection from `working_dir`, and structured `validationResult` metadata for test runs.
