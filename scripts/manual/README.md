# Manual smoke and sandbox scripts

These scripts are intentionally kept outside the repository root so pytest does not collect them as tests. They exercise broader manual endpoint, evaluation, and Custom GPT workflows that may require local services, external repositories, or environment-specific credentials.

Run them from the repository root, for example:

```bash
python scripts/manual/manual_endpoint_sandbox.py
python scripts/manual/manual_coding_task_golden_flow.py
python scripts/manual/manual_phase6_regression_test.py
```

Every script is import-safe and only executes from its `if __name__ == "__main__"` guard.
