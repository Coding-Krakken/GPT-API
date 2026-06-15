---
id: gpt-api-schema-securityschemes-guard-20260609
status: open
severity: high
area: schema
created: 2026-06-15
resolved:
---

# Schema guard false positive on securitySchemes.ApiKeyAuth

## Issue
The YAML schema generator correctly emitted a `components.securitySchemes.ApiKeyAuth:` object, but the guard rejected any line equal to `ApiKeyAuth:`.

## Error
```text
AssertionError: [(3715, '    ApiKeyAuth:')]
```

## Explanation
This line is valid when defining the security scheme object:

```yaml
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: x-api-key
```

The invalid form to reject is only a security requirement entry like:

```yaml
- ApiKeyAuth:
```

## Fix
Change validation to reject lines matching `- ApiKeyAuth:` without `[]`, while allowing `components.securitySchemes.ApiKeyAuth:`.
