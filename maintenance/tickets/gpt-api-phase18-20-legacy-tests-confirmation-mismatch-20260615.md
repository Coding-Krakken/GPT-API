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
