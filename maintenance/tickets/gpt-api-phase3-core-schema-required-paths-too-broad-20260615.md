---
id: "gpt-api-phase3-core-schema-required-paths-too-broad-20260615"
status: "resolved"
severity: "medium"
area: "deployment"
created: "2026-06-15"
resolved_at: "2026-06-15"
resolved_by_commit: "7d08276"
verification_command: "python3 scripts/verify_deployment.py --allow-dirty --output-dir /tmp/gpt-api-deploy-phase3"
verification_result: "passed"
resolution_summary: "Split full coding schema and core Action schema required path contracts."
---

# Maintainer Ticket: Phase 3 deployment verifier used over-broad required path set for core schema

## Issue
During Phase 3 deployment verification implementation, the first run of `scripts/verify_deployment.py --allow-dirty --output-dir /tmp/gpt-api-deploy-phase3` failed because the script applied the same required Coding GPT path set to both `coding-openapi.yaml` and `coding-gpt-core-openapi.yaml`.

## Observed output
```text
ok schema_coding-openapi.yaml: coding-openapi.yaml validated path_count=118
not ok schema_coding-gpt-core-openapi.yaml: coding-gpt-core-openapi.yaml failed deployment schema checks
not ok in_process_/coding-gpt-core-openapi.yaml_served: HTTP 200 path_count=32
```

## Root cause
The full coding schema and the core Action schema have different intended route surfaces. The full schema should include dispatcher convenience routes such as `/coding/env/action`, while the core schema is intentionally smaller and should require only direct core typed endpoints.

## Impact
The verifier produced a false negative. No service files were corrupted.

## Fix plan
Split required-path contracts into:
- full coding schema required paths
- core schema required paths

Then rerun the verifier and targeted tests.
