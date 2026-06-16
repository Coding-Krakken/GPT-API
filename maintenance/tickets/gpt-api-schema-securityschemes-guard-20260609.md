---
id: "gpt-api-schema-securityschemes-guard-20260609"
status: "resolved"
severity: "medium"
area: "schema"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified securitySchemes.ApiKeyAuth guard passes."
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
