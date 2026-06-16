---
id: "openapi_python_permission_1781485780"
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

# Maintainer Ticket: Local Python sandbox cannot access `/root/GPT-API/openapi.yaml`

## Description
A private Python execution attempt failed because the sandbox process did not have permission to read `/root/GPT-API/openapi.yaml`.

## Attempted action
```python
from pathlib import Path
p = Path('/root/GPT-API/openapi.yaml')
spec = yaml.safe_load(p.read_text())
```

## Error
```text
PermissionError: [Errno 13] Permission denied: '/root/GPT-API/openapi.yaml'
```

## Context
The repository-control endpoints can read and write files under `/root/GPT-API`, but the local Python sandbox cannot. Workaround: write the patch script through `/files` and execute it through `/shell` from inside `/root/GPT-API`.
