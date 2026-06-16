---
id: "gpt-api-phase2-validation-command-empty-failure-20260615"
status: "resolved"
severity: "medium"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "8dd867b"
verification_command: "python3 scripts/ticket_index.py"
verification_result: "ticket index metadata normalized"
resolution_summary: "Combined validation command failed because newly added tickets lacked required lifecycle front matter; ticket metadata normalized."
---

# Maintainer Ticket: Phase 2 validation command exited nonzero without captured output

## Issue
After creating the in-progress dirty-tree ticket, the combined validation command exited with status 1 and no captured stdout/stderr.

## Command

```bash
cd /root/GPT-API && cp /tmp/gpt-api-phase2-release-gate-dirty-tree-20260615.md maintenance/tickets/ && python3 scripts/ticket_index.py >/tmp/ticket_index_phase2_dirty.out && ALLOW_DIRTY=true ./scripts/release_gate.sh && pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py && git status --short --branch && git diff --stat
```

## Observed response

```json
{"stdout":"","stderr":"","exit_code":1,"status":400}
```

## Context
The lack of captured output makes the failing sub-step unclear. The next step is to run the command in smaller pieces and inspect `/tmp/ticket_index_phase2_dirty.out` and release-gate temp outputs.
