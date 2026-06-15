---
id: gpt-api-command-too-long-20260609-schema-yaml
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
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
