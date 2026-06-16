---
id: "gpt-api-phase18-20-codeops-multipath-test-20260615"
status: "open"
severity: "high"
area: "codeops"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add /code regression tests for inferred language, repo-root pytest, PYTHONPATH, and argv selectors."
verification_result: "not_run"
resolution_summary: "codeOps test-mode robustness remains actionable and should be fixed in Phase 2."
---

# Maintainer Ticket: codeOps test endpoint treats multi-file pytest selector as one path

## Issue
While validating Phase 18-20 changes in `/root/GPT-API`, a structured `codeOps` test call with multiple pytest files in the `path` field was interpreted as a single file path and returned `file_not_found`.

## Attempted path
```text
tests/test_shell.py tests/test_files.py tests/test_git.py tests/test_package.py tests/test_batch.py tests/test_code.py tests/test_refactor.py tests/test_apps.py
```

## Error
```json
{"code":"file_not_found"}
```

## Workaround
Run pytest directly through `/shell` for multi-file selectors.
