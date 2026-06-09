# Coding GPT Knowledge: Evaluation and Debug Ingestion

Use `/evals/ingest-debug-log` when a real Custom GPT Actions run fails and the debug transcript is available.

## Ingest a debug log

```json
{
  "log_text": "<paste Custom GPT debug transcript>",
  "write_events": true,
  "create_regression": true
}
```

The backend will parse endpoint calls, classify failure layers, write an evaluation report, and optionally create a regression fixture.

## Common failure layers

- `authentication`: missing/invalid `x-api-key`
- `user_approval`: action needs approval
- `public_tunnel`: wrong/offline ngrok domain
- `schema`: schema shape or operation-limit issue
- `instructions`: GPT instruction-size or behavior issue
- `custom_gpt_behavior`: payload/tool-use/recovery mistake
- `backend_route`: route-level failure
- `repo_environment`: missing dependencies or repo setup issue

## What to do with results

Use the report recommendations to decide whether to update instructions, knowledge, schema, backend code, repo environment, or tunnel/auth setup. If a regression is created, keep it in `evals/regressions/` and run it before shipping future changes.
