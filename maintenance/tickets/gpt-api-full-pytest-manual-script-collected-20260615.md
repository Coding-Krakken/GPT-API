# Maintainer Ticket: Full pytest collected manual smoke script and exited

## Issue
Running full `pytest -q` collected `manual_elevate_smoke_endpoint_test.py`, which executes top-level code and raises `SystemExit` during collection.

## Command

```bash
cd /root/GPT-API
pytest -q
```

## Error

```text
File "/root/GPT-API/manual_elevate_smoke_endpoint_test.py", line 15, in <module>
raise SystemExit(...)
SystemExit: 0
```

## Next action
Constrain pytest collection to real test modules, excluding root-level `manual_*.py` smoke scripts.
