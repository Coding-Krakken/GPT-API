# Maintainer Ticket: HTTP fetch of ngrok schema returned HTML interstitial

## Issue
During schema error triage, fetching the ngrok schema over HTTP returned an HTML page instead of `openapi.yaml`, causing YAML parsing to fail.

## Attempted command

```bash
curl -L --max-time 30 -H 'ngrok-skip-browser-warning: true' -sS http://unscrutinized-immotile-jermaine.ngrok-free.dev/openapi.yaml -o /tmp/live_openapi_http.yaml
```

## Observed output

The response started with:

```html
<!doctype html> <html lang="en">
```

Parsing failed with:

```text
yaml.scanner.ScannerError: while scanning for the next token
found character '\t' that cannot start any token
```

## Context
HTTPS fetch also failed from this environment with TLS errors. Localhost/backend schema verification is needed to isolate whether the live backend process or ngrok transport is stale/misconfigured.
