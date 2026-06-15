---
id: gpt-api-phase1-3-test-edit-heredoc-error-20260614
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
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
