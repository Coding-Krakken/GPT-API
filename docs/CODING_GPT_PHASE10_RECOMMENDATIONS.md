# Coding GPT Phase 10: Improvement Recommendation Engine

Phase 10 ranks high-ROI improvements after every evaluation run. It turns telemetry, scorecards, classified failures, endpoint stats, and backend engine metrics into evidence-backed recommendations.

## Goals

- Identify the highest ROI improvement opportunities.
- Group recommendations by likely owner layer: safety, schema, instructions, Custom GPT behavior, backend engine, backend route, repo environment, or evaluation.
- Attach evidence to every recommendation.
- Expose recommendations in JSON reports, Markdown reports, and API responses.

## Inputs

The engine consumes:

- telemetry events
- agent scorecard
- backend scorecard
- classified failures
- endpoint latency/reliability stats
- backend engine metrics

## Output shape

```json
{
  "version": "phase10_recommendation_engine_v1",
  "summary": {
    "recommendation_count": 3,
    "top_priority": "Improve missing dependency diagnosis and environment guidance",
    "failure_code_counts": {"dependency_missing": 1},
    "failure_layer_counts": {"repo_environment": 1}
  },
  "ranked": [
    {
      "priority": 1,
      "title": "Improve missing dependency diagnosis and environment guidance",
      "layer": "backend_engine/repo_environment",
      "roi_score": 94,
      "impact": "medium",
      "effort": "low",
      "severity": "medium",
      "affected_metrics": ["quality_engine", "test_engine", "communication"],
      "evidence": {"exit_127_count": 1},
      "action_items": ["Classify exit code 127 as dependency_missing"]
    }
  ],
  "grouped": {
    "backend_engine": []
  }
}
```

## Ranking model

Recommendations are ranked by a deterministic ROI score derived from:

- impact
- severity
- implementation effort
- frequency/evidence count
- confidence

Low-effort, high-impact, safety-sensitive or repeated issues rise to the top.

## API

Generate recommendations from an existing report or filtered telemetry:

```http
POST /evals/recommendations
```

Example:

```json
{
  "report_id": "release_gate_20260609_001",
  "top_n": 10
}
```

## Report integration

`evals/report.py` now includes:

- `recommendation_engine`
- `recommendations`
- `recommendations_grouped`

Markdown reports include ROI score, owner layer, evidence summary, affected metrics, and first action items.

## Acceptance criteria

Phase 10 is complete when:

- Every generated eval report includes ranked recommendations.
- Recommendations include evidence.
- Recommendations are grouped by owner layer.
- `/evals/recommendations` returns top recommendations from a report or telemetry filter.
- Release gate reports include the recommendation output through the eval report artifact.
- Recommendation generation is deterministic for the same events.
