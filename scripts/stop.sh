#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ ! -f run/gpt-api.pid ]; then
  echo "gpt-api pid file not found"
  exit 0
fi
PID="$(cat run/gpt-api.pid)"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi
  echo "stopped gpt-api pid=$PID"
else
  echo "gpt-api pid=$PID not running"
fi
rm -f run/gpt-api.pid
