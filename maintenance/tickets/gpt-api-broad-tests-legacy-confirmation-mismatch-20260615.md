---
id: "gpt-api-broad-tests-legacy-confirmation-mismatch-20260615"
status: "resolved"
severity: "medium"
area: "maintenance"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified full pytest passes with dangerous-operation confirmation policy."
---

# Maintainer Ticket: Broad legacy tests conflict with dangerous-operation confirmation policy

## Issue
After phase suites and release gate passed, broader legacy endpoint tests failed because they expect dangerous operations to run without explicit confirmation. The current Phase 18 policy intentionally blocks these operations unless `confirm: true` or an equivalent confirmation string is provided.

## Failed categories

- `/shell` background start without confirmation
- `/files` delete/restore overwrite without confirmation
- `/git` checkout/reset/rebase without confirmation
- `/package` install/remove/update/upgrade without confirmation
- `/apps` launch/kill without confirmation
- `/batch` rollback delete without confirmation

## Decision
Do not weaken the safety policy. Update legacy tests that intentionally exercise guarded operations to include explicit confirmation, and keep policy tests verifying that unconfirmed dangerous operations are blocked.

## Additional real failure
`tests/test_coding_safety_boundaries.py::test_blocked_patch_path_is_rejected` showed `.env` patch preview was not rejected and requires an implementation fix.
