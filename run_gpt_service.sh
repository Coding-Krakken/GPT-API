#!/bin/bash
set -euo pipefail

cd /root/GPT-API
mkdir -p logs

# Kill previously tracked ngrok tunnel
if [ -f /run/ngrok.pid ]; then
  PID=$(cat /run/ngrok.pid)
  if ps -p "$PID" | grep -q ngrok; then
    kill "$PID" && echo "[x] Stopped tracked ngrok process (PID=$PID)"
  else
    echo "[i] ngrok PID file exists but process not running"
  fi
  rm -f /run/ngrok.pid
else
  echo "[i] No ngrok PID file found"
fi

# Kill anything on port 8000 (stale backend)
PID=$(lsof -ti :8000) && kill "$PID" && echo "[x] Stopped process on port 8000 (PID=$PID)" || echo "[i] Nothing was using port 8000"
sleep 2

# Start ngrok and track PID. Force stdout logging so tunnel lifecycle and
# errors are visible to diagnostics instead of leaving an empty log file.
ngrok start --all --log=stdout >> logs/ngrok.log 2>&1 &
echo $! > /run/ngrok.pid
sleep 5

# Activate venv and run backend
source /root/GPT-API/.venv/bin/activate
exec python /root/GPT-API/cli.py >> logs/gpt-cli.log 2>&1
