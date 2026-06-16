---
id: "gpt-api-schema-guard-error-20260609-github-prefix"
status: "resolved"
severity: "medium"
area: "schema"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified schema validation passes after route-prefix guard fixes."
---

# Schema guard error: `/github` incorrectly matched as `/git`

## Issue
While regenerating JSON-formatted OpenAPI schemas, the safety guard used `p.startswith('/git')`, which incorrectly treated `/github/issue/read` as forbidden raw `/git` access.

## Error
```text
AssertionError: /github/issue/read
```

A follow-up parser command then failed because schema generation aborted before writing both files consistently:

```text
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Fix
Regenerate schemas using segment-aware forbidden path checks:

```python
p == forbidden or p.startswith(forbidden + '/')
```

This blocks `/git/...` while allowing `/github/...`.
