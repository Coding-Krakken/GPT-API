---
id: gpt-api-full-pytest-manual-script-systemexit-20260614
status: open
severity: low
area: endpoint
created: 2026-06-15
resolved:
---

# Maintainer Ticket: Full pytest collects manual smoke script and exits during import

## Issue
Running full repository pytest from `/root/GPT-API` failed during collection because `manual_elevate_smoke_endpoint_test.py` executes code at import time and raises `SystemExit`.

## Command
```bash
cd /root/GPT-API && .venv/bin/python -m pytest -q
```

## Error summary
```text
File "/root/GPT-API/manual_elevate_smoke_endpoint_test.py", line 15, in <module>
    raise SystemExit(...)
SystemExit: 0
mainloop: caught unexpected SystemExit!
```

## Context
The script printed a successful smoke report before exiting, but pytest treats import-time `SystemExit` as an internal collection error.

## Suggested fix
Move manual smoke scripts out of pytest discovery scope, rename them so they are not collected, or guard executable code with:

```python
if __name__ == "__main__":
    ...
```

## Workaround
Run the real test suite with:

```bash
.venv/bin/python -m pytest -q tests
```
