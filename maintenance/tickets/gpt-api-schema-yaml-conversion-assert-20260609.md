---
id: "gpt-api-schema-yaml-conversion-assert-20260609"
status: "resolved"
severity: "medium"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified all schema YAML files validate."
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
