---
id: "gpt-api-phase1-3-test-edit-heredoc-error-20260614"
status: "obsolete"
severity: "low"
area: "environment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Phase 1-3 test edit command heredoc syntax error

## Issue
During implementation of GPT-API Phases 1-3, a combined shell command intended to edit `tests/test_phase1_phase3_route_normalization.py` and then run pytest accidentally placed the pytest invocation inside the Python heredoc.

## Command shape
```bash
cd /root/GPT-API && python3 - <<'PY'
...
p.write_text(s)
.venv/bin/python -m pytest -q tests/test_phase1_phase3_route_normalization.py
```

## Error
```text
SyntaxError: invalid syntax
```

## Impact
No service files were affected by this command. The test file edit may not have been applied because Python parsing failed before execution.

## Workaround
Run the Python edit heredoc and pytest as separate shell statements after closing `PY`.
