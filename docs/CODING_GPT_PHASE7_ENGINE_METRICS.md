# Coding GPT Phase 7: Backend Engine Quality Metrics

Phase 7 adds backend-engine-specific evaluation metrics so reports can distinguish route availability from actual engine quality.

## Engines measured

- repo intelligence
- workspace/worktree engine
- patch engine
- test and quality engine
- policy engine

## Metrics source

Metrics are computed from sanitized telemetry events in `/tmp/gpt-api-evals/events.jsonl`. The report generator aggregates those events into JSON and Markdown reports.

## New module

```text
evals/engine_metrics.py
```

It exposes:

```text
engine_metrics(events)
engine_scores(metrics)
repo_intelligence_metrics(events)
workspace_metrics(events)
patch_engine_metrics(events)
test_quality_metrics(events)
policy_metrics(events)
```

## Report output

Every eval report now includes:

```json
{
  "scores": {
    "engines": {
      "overall": 99,
      "subscores": {
        "repo_intelligence": 100,
        "workspace": 100,
        "patch_engine": 100,
        "test_quality_engine": 95,
        "policy_engine": 100
      }
    }
  },
  "engine_metrics": {
    "repo_intelligence": {},
    "workspace": {},
    "patch_engine": {},
    "test_quality_engine": {},
    "policy_engine": {}
  }
}
```

Markdown reports include a `Backend engine metrics` section.

## New benchmark case

```text
evals/cases/backend_engine_metrics.yaml
```

Suites:

```text
backend_engine_metrics
phase7_backend_engines
release_gate
```

Run manually:

```bash
python evals/run_eval_suite.py --suite backend_engine_metrics --repo-path /home/obsidian/Elevate_test
```

Expected result:

```text
1/1 case passed
engine metrics present
engine scores present
```

## Telemetry improvements

Phase 7 adds or uses explicit events for:

```text
repo_overview_completed
repo_instructions_completed
repo_relevant_context_completed
repo_route_map_completed
workspace_created
workspace_status_checked
workspace_diff_checked
workspace_diff_summary
patch_previewed
patch_applied
patch_reverted
patch_risk_validated
tests_discovered
tests_run
quality_run
subprocess_completed
policy_path_checked
policy_evaluated
```

## Validation result

Validated against `/home/obsidian/Elevate_test` with:

```bash
python evals/run_eval_suite.py --suite backend_engine_metrics --repo-path /home/obsidian/Elevate_test --report-id phase7_backend_engine_metrics_manual
```

Result:

```text
status: 200
total: 1
passed: 1
failed: 0
agent_score: 100
backend_score: 99
engine overall score: 99
report_json: /tmp/gpt-api-evals/reports/phase7_backend_engine_metrics_manual.json
report_md: /tmp/gpt-api-evals/reports/phase7_backend_engine_metrics_manual.md
```

## Completion criteria

Phase 7 is complete when:

- engine metrics module exists
- reports include engine metrics and engine scores
- repo/workspace/patch/test-quality/policy engines are represented
- a dedicated backend engine metrics eval case exists
- the Phase 7 eval suite passes against `/home/obsidian/Elevate_test`
- changes are committed and pushed
