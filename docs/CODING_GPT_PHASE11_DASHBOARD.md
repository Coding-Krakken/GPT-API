# Coding GPT Phase 11: Evaluation Dashboard

Phase 11 is the review surface for the Coding GPT evaluation system. It makes eval reports easy to inspect, compare, and trend over time.

## Implemented components

- `evals/dashboard.py`: report index, latest report loader, trend summaries, comparison helpers, HTML renderer, Markdown renderer.
- `/evals/dashboard`: HTML dashboard for recent evaluation reports.
- `/evals/dashboard.md`: Markdown dashboard.
- `/evals/dashboard/summary`: JSON report list with filters.
- `/evals/dashboard/latest`: latest full report and summary.
- `/evals/dashboard/trend`: score/failure trend points.
- `/evals/dashboard/report/{report_id}`: full JSON report detail.
- `/evals/dashboard/compare`: compare two reports.

## Dashboard endpoints

### HTML dashboard

```text
GET /evals/dashboard?limit=25
```

Returns an HTML page with latest score cards, recent reports, and trend table.

### Markdown dashboard

```text
GET /evals/dashboard.md?limit=25
```

Returns a Markdown dashboard suitable for logs, terminals, or knowledge capture.

### JSON summary

```text
GET /evals/dashboard/summary?limit=25
```

Optional filters:

```text
repo_path
task_id
min_agent_score
min_backend_score
failure_layer
endpoint
```

### Latest report

```text
GET /evals/dashboard/latest
```

Returns the newest report summary plus full report JSON.

### Trend

```text
GET /evals/dashboard/trend?limit=20
```

Returns ordered score/failure trend points.

### Report detail

```text
GET /evals/dashboard/report/{report_id}
```

Returns one full report.

### Compare reports

```text
GET /evals/dashboard/compare?current_report_id=<current>&baseline_report_id=<baseline>
```

Returns score deltas, failure-count delta, new failure codes, and fixed failure codes.

## Storage

Reports are loaded from:

```text
/tmp/gpt-api-evals/reports/*.json
```

This keeps Phase 11 simple and compatible with the existing JSON/Markdown report system. SQLite can be added later without changing the API shape.

## Acceptance criteria

- Latest evaluation is visible from `/evals/dashboard`.
- Markdown dashboard is available.
- JSON summary supports filtering by repo, task, failure layer, endpoint, and minimum scores.
- Trend endpoint shows score/failure changes over recent reports.
- Compare endpoint identifies score deltas, new failures, and fixed failures.
- Dashboard endpoints are protected by the existing `x-api-key` auth dependency.
