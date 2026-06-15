# Coding GPT Phase 8: Real Custom GPT Trace Ingestion

Phase 8 captures and evaluates actual Custom GPT behavior from pasted Actions debug logs.

## What it solves

Backend tests prove the API works, but real Custom GPT runs can still fail because of action authentication, approval prompts, wrong schema domains, missing dispatcher payloads, or poor recovery behavior. Phase 8 turns those transcripts into structured evaluation data.

## Endpoints

### POST `/evals/ingest-debug-log`

Input:

```json
{
  "log_text": "...pasted Custom GPT Actions debug transcript...",
  "source": "custom_gpt_debug",
  "write_events": true,
  "create_regression": true
}
```

Output includes:

- parsed action calls
- failure codes
- failure layers
- recommendations
- JSON/Markdown debug ingest reports
- optional regression file
- telemetry events written to eval JSONL

### POST `/evals/debug-log/regression`

Creates a regression fixture directly from a pasted debug transcript.

## Failure layers

The ingester classifies failures into layers such as:

- `authentication`
- `user_approval`
- `public_tunnel`
- `schema`
- `instructions`
- `custom_gpt_behavior`
- `backend_route`
- `backend_engine`
- `repo_environment`
- `policy`

## Recognized failures

Current detection includes:

- missing or invalid `x-api-key`
- action requires approval
- wrong/offline ngrok domain
- ngrok `ERR_NGROK_3200`
- `missing_payload_fields`
- unsupported action/category
- Custom GPT schema operation limit
- invalid `ApiKeyAuth` list shape
- instructions over the Custom GPT limit
- `ClientResponseError`
- missing dependencies such as `command not found` or exit code 127

## Reports

Reports are written under:

```text
/tmp/gpt-api-evals/debug_ingests/<run_id>.json
/tmp/gpt-api-evals/debug_ingests/<run_id>.md
```

When `write_events` is enabled, normalized events are appended to:

```text
/tmp/gpt-api-evals/events.jsonl
```

## Regression generation

When `create_regression` is true, the ingester writes a reusable regression under:

```text
evals/regressions/debug_<failure_code>_<timestamp>.yaml
```

This makes real Custom GPT failures part of the permanent regression suite.
