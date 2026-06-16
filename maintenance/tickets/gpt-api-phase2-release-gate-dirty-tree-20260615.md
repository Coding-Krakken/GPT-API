---
id: "gpt-api-phase2-release-gate-dirty-tree-20260615"
status: "resolved"
severity: "medium"
area: "release"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "4237779"
verification_command: "python3 scripts/ticket_index.py"
verification_result: "ticket index metadata normalized"
resolution_summary: "Expected in-progress validation ordering issue; rerun release gate with ALLOW_DIRTY=true before commit and clean release gate after commit."
---

# Maintainer Ticket: Phase 2 release gate blocked by in-progress dirty tree

## Issue
During Phase 2 `/code` test-mode implementation, `./scripts/release_gate.sh` was run before committing the intentional edits. The release gate exited nonzero because it enforces a clean git tree unless `ALLOW_DIRTY=true` is set.

## Command

```bash
cd /root/GPT-API && python3 /tmp/update_phase2_tickets.py && python3 scripts/ticket_index.py >/tmp/ticket_index_phase2.out && python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py && git status --short --branch && git diff --stat
```

## Observed behavior
OpenAPI validation passed, then `release_gate.sh` printed a git diff and exited because the working tree contained the in-progress Phase 2 edits.

## Context
This is expected behavior for the release gate. For in-progress validation, rerun with `ALLOW_DIRTY=true`; after committing, rerun the standard release gate without `ALLOW_DIRTY`.

## Resolution plan
1. Copy this ticket into `maintenance/tickets/`.
2. Rerun validation with `ALLOW_DIRTY=true` while dirty.
3. Commit Phase 2.
4. Rerun standard clean release gate after commit.
