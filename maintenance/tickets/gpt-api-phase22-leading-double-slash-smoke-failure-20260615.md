---
id: "gpt-api-phase22-leading-double-slash-smoke-failure-20260615"
status: "resolved"
severity: "medium"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified scripts/smoke_local.py covers duplicate-slash normalization."
---

# Maintainer Ticket: Phase 22 smoke matrix exposed leading double-slash 404

## Issue
The new Phase 22 smoke verification script failed on the leading duplicate slash path `//agent/coding-task`.

## Command

```bash
python3 scripts/smoke_local.py
```

## Error

```text
smoke verification failed: //agent/coding-task: duplicate slash should not be 404
```

## Context
Repository: `/root/GPT-API`
Branch: `feature/coding-gpt-safe-agent`

## Next action
Inspect FastAPI/TestClient path handling for leading `//` paths and either fix middleware normalization or adjust the verification matrix only if the client stack cannot send that path shape in-process.
