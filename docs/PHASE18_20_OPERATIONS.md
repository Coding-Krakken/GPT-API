# Phase 18-20 Operations Hardening

## Phase 18: dangerous-operation policy

Dangerous operations now require explicit confirmation through either `confirm: true` or a `confirmation` string such as `confirmed` or `i understand`.

Guarded operations include:

- `/shell`: sudo, destructive shell patterns, process kills, service stop/restart, filesystem format commands, and background starts.
- `/files`: delete, recursive delete, move-overwrite, and restore-overwrite.
- `/git`: push, clean, reset, checkout, rebase, merge, and stash.
- `/package`: install, remove, update, upgrade, sync, global package changes, and system package managers.
- `/apps`: launch and kill.
- `/code`: install, fix, and format.
- `/refactor`: non-preview apply operations.
- `/batch`: direct shell, package, and refactor execution paths are also guarded.

Policy decisions are written to `logs/policy-decisions.log`. The policy contract is documented in `config/policy.yaml`.

## Phase 19: process supervision

The repo includes operator scripts:

```bash
./scripts/start.sh
./scripts/stop.sh
./scripts/restart.sh
./scripts/status.sh
```

A systemd unit template is available at:

```text
deploy/systemd/gpt-api.service
```

Install example:

```bash
sudo cp deploy/systemd/gpt-api.service /etc/systemd/system/gpt-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now gpt-api.service
```

## Phase 20: log rotation

A logrotate config is available at:

```text
deploy/logrotate/gpt-api
```

Install example:

```bash
sudo cp deploy/logrotate/gpt-api /etc/logrotate.d/gpt-api
sudo logrotate -d /etc/logrotate.d/gpt-api
```

The rotation policy covers `logs/*.log` and `audit.log`, rotates daily or after 10 MB, keeps 14 rotations, compresses old logs, and uses `copytruncate` so the running service does not need to reopen file handles.
