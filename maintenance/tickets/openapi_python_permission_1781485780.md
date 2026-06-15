---
id: openapi_python_permission_1781485780
status: open
severity: low
area: schema
created: 2026-06-15
resolved:
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
