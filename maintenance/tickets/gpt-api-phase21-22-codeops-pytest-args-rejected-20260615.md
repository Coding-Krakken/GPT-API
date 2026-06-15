---
id: gpt-api-phase21-22-codeops-pytest-args-rejected-20260615
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer Ticket: codeOps rejected targeted pytest arguments during Phase 21/22 validation

## Issue
While validating Phase 21/22 changes in `/root/GPT-API`, the structured `/code` test endpoint rejected a targeted pytest argument string.

## Attempted request

```text
action=test
language=python
path=/root/GPT-API
args=-q tests/test_phase16_focused_contracts.py tests/test_phase21_phase22_documentation_verification.py tests/test_phase15_release_gate.py
```

## Error

```json
{"error":{"code":"invalid_args","message":"Unsupported, malformed, or unsafe arguments."},"status":400}
```

## Workaround
Run the same targeted pytest selection through a bounded shell command.
