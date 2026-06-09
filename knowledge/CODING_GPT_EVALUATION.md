# Coding GPT Knowledge: Evaluation and Operations

Use this as a knowledge file for reviewing and improving the Coding GPT system.

## Evaluation layers

Evaluate two systems separately:

1. Custom GPT behavior: state management, tool use, payload discipline, safety, recovery, final answer quality.
2. Backend engines: endpoint reliability, latency, repo intelligence, patching, tests, quality, diagnostics, policy.

## Core commands

Run release gate:

```bash
python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test
```

Run continuous learning cycle:

```bash
python evals/continuous_learning.py --repo-path /home/obsidian/Elevate_test
```

Run Phase 13 production ops:

```bash
python evals/phase13_ops.py --repo-path /home/obsidian/Elevate_test
```

Use `--allow-dirty` only while developing evaluation tooling.

## API endpoints

```text
/evals/run
/evals/report
/evals/compare
/evals/recommendations
/evals/release-gate
/evals/continuous-learning
/evals/ingest-debug-log
/evals/dashboard
/evals/phase13/status
/evals/phase13/run
/evals/phase13/promote-baseline
```

## Real failure loop

Every real failure should become a regression case:

1. Capture the debug transcript or backend trace.
2. Classify the failure layer.
3. Generate a regression fixture.
4. Improve backend/schema/instructions/knowledge.
5. Run release gate.
6. Run Phase 13.
7. Ship only when the system is ship-ready.

## Phase 13

Phase 13 is complete when it produces:

- operational readiness result
- continuous-learning cycle result
- ship/no-ship decision
- optional approved baseline promotion
- release bundle archive
- Markdown and JSON reports
