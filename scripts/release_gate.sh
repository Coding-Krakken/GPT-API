#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ALLOW_DIRTY="${ALLOW_DIRTY:-false}"
if [ "$ALLOW_DIRTY" != "true" ]; then
  git diff --exit-code
  git diff --cached --exit-code
  test -z "$(git ls-files --others --exclude-standard)"
fi

python3 scripts/ticket_index.py >/tmp/gpt_api_ticket_index.out
python3 scripts/validate_openapi.py >/tmp/gpt_api_validate_openapi.out
python3 scripts/smoke_local.py >/tmp/gpt_api_smoke_local.out
pytest -q \
  tests/test_phase14_ticket_triage.py \
  tests/test_phase15_release_gate.py \
  tests/test_phase16_focused_contracts.py \
  tests/test_phase17_error_envelope.py

echo "release gate passed"
