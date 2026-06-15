---
id: gpt-api-codeops-test-language-required-20260614
status: open
severity: high
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer Ticket: codeOps test endpoint requires language for pytest file

## Issue
While implementing GPT-API Phases 1-3, the structured `/code` operation endpoint was used with `action: test` against `tests/test_phase1_phase3_route_normalization.py`, but the request failed validation because `language` was required.

## Attempted request
```json
{
  "action": "test",
  "path": "tests/test_phase1_phase3_route_normalization.py",
  "working_dir": "/root/GPT-API",
  "timeout_seconds": 120,
  "max_output_bytes": 20000
}
```

## Error
```json
{"detail":[{"type":"missing","loc":["body","language"],"msg":"Field required"}]}
```

## Expected
For test actions against an existing `.py` file, the endpoint should infer Python or document that `language: python` is required.

## Workaround
Use `/shell` to run `pytest` directly or include `language: python` in the structured call.
