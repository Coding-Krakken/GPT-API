---
id: "openapi_patch_command_too_long_1781485733"
status: "obsolete"
severity: "low"
area: "patch-safety"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "Current workflow favors file/script endpoints, bounded outputs, and release gate checks."
verification_result: "not_applicable"
resolution_summary: "One-off implementation/tooling incident; mitigated by current workflow and no longer tracked as an active product defect."
---

# Maintainer Ticket: Shell command length limit blocked OpenAPI patch script

## Description
While updating `/root/GPT-API/openapi.yaml`, a generated shell command exceeded the `/shell` endpoint maximum command length of 4096 characters.

## Attempted action
Tried to create and execute a Python patch script inline via `runShellCommand`:

```bash
cd /root/GPT-API && cat > /tmp/strengthen_openapi.py <<'PY'
...large Python script...
PY
python /tmp/strengthen_openapi.py
```

## Error response
```json
{
  "result": {
    "error": {
      "code": "command_too_long",
      "message": "Command exceeds maximum allowed length (4096 characters)."
    },
    "status": 400
  }
}
```

## Context
The intended operation is legitimate OpenAPI schema editing. The workaround is to write the patch script using the `/files` endpoint and then execute the shorter command `python /tmp/strengthen_openapi.py`.

## Environment
Repository: `/root/GPT-API`
File being edited: `/root/GPT-API/openapi.yaml`
