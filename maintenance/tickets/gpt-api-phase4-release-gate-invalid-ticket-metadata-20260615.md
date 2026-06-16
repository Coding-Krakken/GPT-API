---
id: "gpt-api-phase4-release-gate-invalid-ticket-metadata-20260615"
status: "open"
severity: "medium"
area: "maintenance"
created: "2026-06-16"
resolved_at: ""
resolved_by_commit: ""
verification_command: "Add required YAML metadata to new Phase 4 tickets and rerun release gate."
verification_result: "not_run"
resolution_summary: ""
---

# Maintainer Ticket: Phase 4 release gate failed due to invalid ticket metadata

## Issue
During Phase 4 environment bootstrap validation, `ALLOW_DIRTY=true ./scripts/release_gate.sh` exited non-zero after `scripts/ticket_index.py` reported invalid maintainer ticket metadata.

## Repository context
- Repository: `/root/GPT-API`
- Branch: `feature/maintainer-ticket-lifecycle-phase1`
- Working tree intentionally dirty with Phase 4 implementation files.

## Command
```bash
cd /root/GPT-API && python3 scripts/validate_openapi.py && ALLOW_DIRTY=true ./scripts/release_gate.sh && pytest -q tests/test_phase15_release_gate.py tests/test_phase21_phase22_documentation_verification.py tests/test_phase14_ticket_triage.py
```

## Relevant saved output
`/tmp/gpt_api_ticket_index.out`:

```text
tickets_imported_or_present=88
ticket_count=88
invalid_metadata=1
index=/root/GPT-API/maintenance/TICKET_INDEX.md
```

Other release gate components passed before the failure:
- `scripts/check_env.py --strict` returned status `passed` with no strict blockers.
- `scripts/validate_openapi.py` passed all schemas.
- `scripts/smoke_local.py` passed 18 checks.
- `scripts/verify_deployment.py --allow-dirty` passed in-process deployment checks.

## Likely cause
The newly created Phase 4 command-too-long ticket was copied into `maintenance/tickets/` without the YAML metadata fields now enforced by the ticket lifecycle tooling.

## Workaround/fix
Add front matter metadata to the new ticket, regenerate `maintenance/TICKET_INDEX.md`, and rerun the release gate.
