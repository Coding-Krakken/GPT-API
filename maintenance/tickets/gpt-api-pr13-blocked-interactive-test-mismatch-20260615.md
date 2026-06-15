# Maintainer Ticket: PR13 blocked_interactive test mismatch

## Issue
After changing interactive validation prompts to return the requested explicit status `blocked_interactive`, an existing test still expected the previous generic `blocked` status.

## Command

```bash
cd /root/GPT-API && python3 /tmp/fix_pr13_review.py && python3 -m py_compile utils/validation_workflow.py routes/patch.py routes/quality.py tests/test_validation_workflow.py && pytest -q tests/test_validation_workflow.py tests/test_coding_routes.py tests/test_coding_safety_boundaries.py
```

## Failure

```text
FAILED tests/test_validation_workflow.py::test_validation_command_blocks_interactive_prompt
AssertionError: assert 'blocked_interactive' == 'blocked'
```

## Context
The product requirement requested `status: blocked_interactive` for interactive validation blockers. The implementation was updated correctly; the older test assertion needs to be updated to the new contract.
