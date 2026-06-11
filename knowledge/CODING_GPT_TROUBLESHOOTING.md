# Coding GPT Knowledge: Troubleshooting

## Repository context

Repository inspection uses typed repo endpoints. If context is needed, call /repo/instructions, /repo/relevant-context, /repo/search, /repo/read-context, /repo/symbols, or /repo/test-map.

Do not claim repository access is blocked because dispatcher payloads are unavailable.

## 403

Verify x-api-key configuration.

## Quality failures

A quality endpoint can succeed while repository checks fail. Inspect the returned output and continue the workflow.

## Coverage tasks

Generate a measured baseline before modifying thresholds. Required artifacts:
- coverage_baseline
- coverage_report
- coverage_gaps