---
id: gpt-api-schema-generation-error-20260609-apikeyauth
status: open
severity: medium
area: schema
created: 2026-06-15
resolved:
---

# Schema generation error: ApiKeyAuth empty list formatting

## Issue
The Custom GPT Actions importer rejected the generated YAML because `security` entries were emitted as blank YAML values:

```yaml
security:
  - ApiKeyAuth:
```

OpenAPI requires the value to be an array:

```yaml
security:
  - ApiKeyAuth: []
```

## Attempted fix
A custom YAML emitter was updated to preserve empty lists. The attempt succeeded for part of the full schema but still failed on the core schema generation guard.

## Error context
Command attempted from `/root/GPT-API`:

```bash
python - <<'PY'
# regenerated coding-openapi.yaml and coding-gpt-core-openapi.yaml using custom YAML dumper
PY
```

Observed output:

```text
coding-gpt-core-openapi.yaml blank= 20 list= 0
coding-openapi.yaml blank= 1 list= 93
AssertionError
```

## Next step
Switch to writing the schemas as JSON OpenAPI documents saved with `.yaml` names. JSON is a valid OpenAPI serialization and preserves `"ApiKeyAuth": []` exactly.
