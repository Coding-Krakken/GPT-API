---
id: "gpt-api-phase4-case-loader-relative-path-20260609"
status: "resolved"
severity: "medium"
area: "maintenance"
created: "2026-06-15"
resolved_at: "2026-06-16"
resolved_by_commit: "ebc87f8957faef1e780d3275404ef298bf7c6c05"
verification_command: "python3 scripts/validate_openapi.py && ./scripts/release_gate.sh && python3 scripts/smoke_local.py && pytest -q"
verification_result: "passed"
resolution_summary: "Verified phase 4-7 contract tests pass."
---

# Phase 4 case loader relative path bug

## Issue
`manual_phase4_case_test.py` failed when calling `case_loader.load_case(Path('evals/cases') / '<case>.yaml')` because `load_case()` attempted `p.relative_to(REPO_ROOT)` on a relative path.

## Error
```text
ValueError: 'evals/cases/core_smoke.yaml' is not in the subpath of '/root/GPT-API'
```

## Impact
Phase 4 validation could not proceed until case paths are resolved before computing `source_file`.

## Fix
Update `evals/case_loader.py` so `load_case()` resolves relative paths against the repo root, then uses the resolved path for `relative_to(REPO_ROOT)`.
