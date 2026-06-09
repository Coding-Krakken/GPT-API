# Coding GPT Knowledge: Troubleshooting

## 403 from Actions

A 403 means the server was reached but the request did not include a valid `x-api-key` header. Configure the Custom GPT Action authentication as API Key with custom header name `x-api-key`. Do not paste keys into chat.

## ngrok offline or wrong domain

The schema server must be:

```text
https://unscrutinized-immotile-jermaine.ngrok-free.dev
```

If the GPT calls another domain, re-import the latest core schema.

## missing_payload_fields

The dispatcher was called without required values inside `payload`. Read `error.required_payload`, `error.received_payload_keys`, and `error.example_payload`, then retry once with the corrected `payload` object.

## Quality command fails but endpoint works

If `/coding/quality/action` returns status 200 with `passed:false`, the endpoint worked. The repository command failed. For example, `eslint: command not found` means dependencies are missing. Use `/coding/env/action` with `prepare_dry_run` to plan environment setup, then ask the user before any network-writing install.

## Consequential action approval

Some Custom GPT calls may require approval even when safe. After approval, the call should continue. Use the smoke-test endpoint for endpoint validation to minimize repeated approvals.

## Do not bypass policy

Never ask for shell, unrestricted file access, package installation, arbitrary git, or secret reads. The Coding GPT must stay inside the safe action API.
