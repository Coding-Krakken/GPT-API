---
id: "gpt-api-phase18-20-codeops-multipath-test-20260615"
status: "resolved"
severity: "high"
area: "codeops"
created: "2026-06-16"
resolved_at: "2026-06-15"
resolved_by_commit: "4237779"
verification_command: "pytest -q tests/test_code_phase2.py tests/test_code.py tests/test_code_api_hardening.py tests/test_code_content_edge_cases.py tests/test_expanded_endpoint_contract.py tests/test_phase15_release_gate.py"
verification_result: "50 passed, 1 warning"
resolution_summary: "Phase 2 implemented robust /code test mode: language inference, repo-root pytest, working_dir PYTHONPATH, multi-file argv/selectors, and validationResult output."
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


## Phase 2 resolution

Implemented and verified in Phase 2. `/code` test mode now supports inferred Python language for pytest files and repo roots, repository-root pytest execution, safe multi-file pytest selectors through `argv` or `args`, `PYTHONPATH` injection from `working_dir`, and structured `validationResult` metadata for test runs.
