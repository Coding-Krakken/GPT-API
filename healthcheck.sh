#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-5}"

check_path() {
  local path="$1"
  local url="${BASE_URL%/}${path}"
  local code
  code="$(curl -fsS --max-time "$TIMEOUT_SECONDS" -o /tmp/gpt-api-healthcheck-response.json -w '%{http_code}' "$url")"
  if [ "$code" != "200" ]; then
    echo "healthcheck failed: $url returned HTTP $code" >&2
    cat /tmp/gpt-api-healthcheck-response.json >&2 || true
    return 1
  fi
}

check_path /health
check_path /healthz
check_path /api/health

echo "gpt-api healthcheck passed base_url=$BASE_URL"
