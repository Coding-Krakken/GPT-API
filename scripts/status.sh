#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ -f run/gpt-api.pid ]; then
  PID="$(cat run/gpt-api.pid)"
  if kill -0 "$PID" 2>/dev/null; then
    ps -p "$PID" -o pid,etime,pcpu,pmem,args
    exit 0
  fi
fi
PIDS="$(pgrep -f 'python .*cli.py|python .*main.py' || true)"
if [ -n "$PIDS" ]; then
  ps -p "$(echo "$PIDS" | paste -sd, -)" -o pid,etime,pcpu,pmem,args
else
  echo "gpt-api not running"
fi
