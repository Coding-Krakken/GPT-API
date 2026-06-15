---
id: gpt-api-schema-yaml-conversion-assert-20260609
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
---

# Schema YAML conversion assertion

## Issue
While converting schemas from JSON-formatted OpenAPI to YAML-style OpenAPI with an explicit server block, the script successfully converted `coding-gpt-core-openapi.yaml` but hit an assertion while processing the second schema.

## Goal
Set the schema server block exactly like:

```yaml
servers:
  - url: "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
```

and preserve valid OpenAPI security arrays:

```yaml
security:
  - ApiKeyAuth: []
```

## Observed partial result
`coding-gpt-core-openapi.yaml` now contains:

```text
servers:
  - url: "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
security:
  - ApiKeyAuth: []
```

## Next step
Finish conversion/validation for `coding-openapi.yaml` using a script that can load either JSON or the simple generated YAML format, then commit/push.
