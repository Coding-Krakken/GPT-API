# Maintainer Ticket: HTTPS fetch of ngrok schema failed during schema error triage

## Issue
While investigating user-reported OpenAPI import errors that still showed old descriptions, attempts to fetch the live schema via HTTPS failed with TLS errors from the local environment.

## Attempted commands

```bash
curl -k -L --max-time 30 -H 'ngrok-skip-browser-warning: true' -sS https://unscrutinized-immotile-jermaine.ngrok-free.dev/openapi.yaml -o /tmp/live_openapi.yaml
```

Python urllib attempt also failed:

```text
URLError(SSLError(1, '[SSL: RECORD_LAYER_FAILURE] record layer failure (_ssl.c:1081)'))
```

Curl error:

```text
curl: (35) TLS connect error: error:0A00010B:SSL routines::wrong version number
```

## Context
Repository `openapi.yaml` at HEAD already has shortened descriptions and `/metrics` properties. This failure may indicate local TLS/ngrok protocol mismatch or an environment-specific network issue while trying to compare the live served schema.

## Workaround
Try HTTP access or inspect/restart the local process that backs the tunnel, then fetch through localhost where possible.
