---
id: gpt-api-script-error-20260609-task-ledger-redaction
status: open
severity: high
area: runtime
created: 2026-06-15
resolved:
---

# Script error while adding task artifact redaction

## Issue
A Python one-off patch script intended to modify `/root/GPT-API/utils/task_ledger.py` failed with an `IndentationError` before making the change.

## Command attempted
```bash
cd /root/GPT-API && python - <<'PY'
# attempted insertion of _redact_artifact and add_artifact replacement
PY
python -m py_compile utils/task_ledger.py
```

## Error
```text
IndentationError: unexpected indent
```

## Impact
The redaction/size-limit change was not applied in that failed attempt. The file still needs to be patched using a simpler method.

## Context
This occurred during implementation of the Custom-GPT-first strict protocol layer after successfully adding:

- task protocol helpers
- `/tasks/validate-artifacts`
- `/tasks/phase-contract`
- `/tasks/iteration-summary`
- `/agent/coding-task/repair-plan`
- `/agent/coding-task/iteration-summary`
- `/agent/coding-task/contract-report`
- GitHub CI/review contract helpers
