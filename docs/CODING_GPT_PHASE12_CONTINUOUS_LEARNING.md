# Coding GPT Phase 12: Continuous Learning Loop

Phase 12 makes the Coding GPT improvement loop enforceable. It ties every release to telemetry, scorecards, regression coverage, a release gate, baseline comparison, and a ship/no-ship decision.

## Completed capability

Phase 12 adds:

- `evals/continuous_learning.py`
- `/evals/continuous-learning`
- continuous-learning JSON and Markdown reports under `/tmp/gpt-api-evals/continuous_learning/`
- regression coverage checks for known failures
- release-gate execution
- baseline/latest report comparison
- git cleanliness and remote-pushed enforcement when requested
- explicit ship/no-ship decision output

## Command

```bash
python evals/continuous_learning.py --repo-path /home/obsidian/Elevate_test
```

During development of the loop itself, use:

```bash
python evals/continuous_learning.py --repo-path /home/obsidian/Elevate_test --allow-dirty
```

## API

```http
POST /evals/continuous-learning
```

Example:

```json
{
  "repo_path": "/home/obsidian/Elevate_test",
  "require_clean_git": true
}
```

## Ship decision rules

The cycle returns `ship_ready: true` only when:

1. The release gate passes.
2. Known failures have regression coverage.
3. Git is clean and pushed when `require_clean_git` is true.
4. Baseline comparison shows no unacceptable new failures or score regression.

## Known failure regression coverage

The cycle checks that these incident classes have regression files:

- missing dispatcher payload
- wrong ngrok domain
- missing API key
- instructions over 8,000 characters
- Custom GPT operation limit
- OpenAPI `ApiKeyAuth` empty-list schema issue

## Continuous improvement loop

1. Run a real task or evaluation suite.
2. Capture telemetry.
3. Generate scorecards and recommendations.
4. Convert every real failure into a regression case.
5. Improve backend, schema, instructions, or knowledge.
6. Run the release gate.
7. Compare with the baseline.
8. Ship only when the cycle returns `ship_ready: true`, or document an accepted tradeoff.

## Operating rules

- No real failure disappears without a regression case.
- No schema change ships without operation-count and auth validation.
- No instruction change ships without length validation.
- No backend change ships without core smoke and policy checks.
- No claimed improvement ships without before/after report.
- No network-writing behavior is considered safe without explicit approval and policy approval.
