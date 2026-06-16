---
id: "gpt-api-phase14-17-codeops-language-required-20260614"
status: "open"
severity: "high"
area: "codeops"
created: "2026-06-15"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add /code regression tests for inferred language, repo-root pytest, PYTHONPATH, and argv selectors."
verification_result: "not_run"
resolution_summary: "codeOps test-mode robustness remains actionable and should be fixed in Phase 2."
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
