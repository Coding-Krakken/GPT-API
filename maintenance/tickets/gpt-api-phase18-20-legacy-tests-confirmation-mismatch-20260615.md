---
id: "gpt-api-phase18-20-legacy-tests-confirmation-mismatch-20260615"
status: "resolved"
severity: "medium"
area: "environment"
created: "2026-06-16"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified full pytest passes with dangerous-operation confirmation policy."
---

# Maintainer Ticket: Legacy endpoint tests expect dangerous operations without confirmation

## Issue
After implementing Phase 18 safety controls, the broader legacy endpoint test subset fails because many existing tests still expect dangerous operations to run without explicit confirmation.

## Examples
- `/shell` background start now returns `confirmation_required` unless `confirm=true`.
- `/files` delete now returns `confirmation_required` unless `confirm=true`.
- `/git` checkout/reset/rebase/push now require confirmation.
- `/package` install/remove/update/upgrade/sync now require confirmation.
- `/apps` launch/kill now require confirmation after request validation.

## Command
```bash
pytest -q tests/test_shell.py tests/test_files.py tests/test_git.py tests/test_package.py tests/test_batch.py tests/test_code.py tests/test_refactor.py tests/test_apps.py
```

## Result
128 passed, 1 skipped, 37 failed. The failures are policy contract changes, not syntax/import failures.

## Follow-up
Update legacy tests to include `confirm=true` when intentionally exercising dangerous actions, and add separate negative tests for `confirmation_required` responses.
