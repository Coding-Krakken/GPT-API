#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p logs run
if [ -f run/gpt-api.pid ] && kill -0 "$(cat run/gpt-api.pid)" 2>/dev/null; then
  echo "gpt-api already running pid=$(cat run/gpt-api.pid)"
  exit 0
fi
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
source .venv/bin/activate
nohup python cli.py >> logs/gpt-cli.log 2>&1 &
echo $! > run/gpt-api.pid
echo "started gpt-api pid=$!"
