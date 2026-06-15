---
id: gpt-api-validation-ticket-20260609
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer ticket: GPT-API validation transport and environment blockers

Branch: feature/coding-gpt-safe-agent

## Summary
Validation was interrupted by infrastructure/test-environment issues rather than merge conflicts or implementation dead ends.

## Issues observed
- ngrok/control endpoint intermittently returned ERR_NGROK_3004 invalid/incomplete HTTP response.
- Endpoint previously returned ERR_NGROK_3200 offline.
- Endpoint returned ERR_NGROK_8012: ngrok agent could not connect to upstream localhost:8000.
- Longer pytest/tool calls sometimes failed with ClientResponseError before stdout/stderr/exit code returned.
- Large inline shell writes exceeded the 4096-character command limit.
- Fresh environment missed pytest initially, then requests for API/comprehensive tests.
- requirements.txt appears UTF-16 LE; structured UTF-8 read failed.
- Legacy tests assumed non-root runtime and stable live CPU/memory metrics; this container runs as root and metrics fluctuate.

## Completed validation before outage
- Coding GPT tests: 11 passed
- Code/batch tests: 51 passed
- Apps/package/refactor/audit tests: 72 passed
- Shell/files/git/system/monitor: 86 passed, 2 skipped
- Python compile check: passed

Known completed total: 220 passed, 2 skipped.

## Mitigation plan
Use short commands, structured file writes for large files, single-file pytest runs with log files, and avoid long streamed output.
