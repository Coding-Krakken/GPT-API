#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
SKIP_INSTALL="${SKIP_INSTALL:-false}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "bootstrap failed: Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
if [ "$SKIP_INSTALL" != "true" ]; then
  python -m pip install -r requirements.txt
fi

python scripts/check_env.py --strict --check-all-requirements --json-output /tmp/gpt_api_check_env.json
printf 'bootstrap complete: python=%s report=%s\n' "$(command -v python)" "/tmp/gpt_api_check_env.json"
