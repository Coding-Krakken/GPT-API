---
id: "gpt-api-phase2-ticket-index-test-active-codeops-mismatch-20260615"
status: "resolved"
severity: "medium"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "4237779"
verification_command: "ALLOW_DIRTY=true ./scripts/release_gate.sh"
verification_result: "pending rerun"
resolution_summary: "Updated ticket triage test to allow codeOps tickets to be closed after Phase 2."
---

# Maintainer Ticket: Phase 2 ticket-index test expected active codeOps backlog after codeOps closure

## Issue
After Phase 2 resolved the active codeOps tickets, `tests/test_phase14_ticket_triage.py::test_ticket_rows_include_active_and_closed_backlog` still expected at least one active ticket with `area == "codeops"`.

## Command

```bash
python3 scripts/ticket_index.py && ALLOW_DIRTY=true ./scripts/release_gate.sh
```

## Failure

```text
FAILED tests/test_phase14_ticket_triage.py::test_ticket_rows_include_active_and_closed_backlog
assert any(row["area"] == "codeops" for row in active)
```

## Context
This is now stale because Phase 2 intentionally resolved all active codeOps maintainer tickets. The test should verify that codeOps tickets exist in the backlog and may be closed, not require an active codeOps ticket forever.

## Resolution plan
Update the test to assert codeOps rows exist across all parsed rows and that active/closed backlog groups are both represented.
