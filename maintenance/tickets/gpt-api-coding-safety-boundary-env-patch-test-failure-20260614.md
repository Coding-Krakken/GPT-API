---
id: gpt-api-coding-safety-boundary-env-patch-test-failure-20260614
status: open
severity: high
area: schema
created: 2026-06-15
resolved:
---

# Maintainer Ticket: coding safety boundary test allows `.env` patch preview

## Issue
Running the in-process pytest suite, excluding requests-based legacy tests, produced one failure in `tests/test_coding_safety_boundaries.py`.

## Command
```bash
cd /root/GPT-API && .venv/bin/python -m pytest -q tests --ignore=tests/comprehensive_test.py --ignore=tests/test_api.py --ignore=tests/test_full_api.py
```

## Failure
```text
tests/test_coding_safety_boundaries.py::test_blocked_patch_path_is_rejected
assert body["status"] == 400
E assert 200 == 400
```

## Context
The test creates a patch that adds `.env` and expects `/patch/preview` to reject it with status 400. The endpoint returned status 200.

## Relevance to current work
This appears unrelated to Phase 1-3 route normalization, slash aliases, or OpenAPI server URL normalization. The affected endpoint suite passed independently.

## Suggested fix
Review patch path blocking for sensitive files such as `.env`, `.env.*`, private keys, and credential-bearing files in `/patch/preview` and `/patch/apply`.
