---
id: "gpt-api-command-too-long-20260609-schema-yaml"
status: "obsolete"
severity: "low"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Command too long while regenerating schema YAML

## Issue
A shell command to regenerate `coding-openapi.yaml` and `coding-gpt-core-openapi.yaml` as YAML-style OpenAPI exceeded the control API's 4096-character command limit.

## Error
```json
{"code":"command_too_long","message":"Command exceeds maximum allowed length (4096 characters)."}
```

## Intended action
Regenerate both schemas with:

```yaml
servers:
  - url: "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
```

and valid security entries:

```yaml
security:
  - ApiKeyAuth: []
```

## Next step
Write a short generator script file into the repo or `/tmp`, run it, validate, then commit/push.
