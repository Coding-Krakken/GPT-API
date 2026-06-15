---
id: gpt-api-schema-guard-error-20260609-github-prefix
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
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
