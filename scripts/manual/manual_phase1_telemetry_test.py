from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import collections
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = REPO_ROOT
TELEMETRY_ROOT = Path('/tmp/gpt-api-phase1-telemetry-test')
EVENTS = TELEMETRY_ROOT / 'events.jsonl'
REQUIRED_EVENTS = [
    'task_started',
    'dispatcher_called',
    'action_completed',
    'task_phase_selected',
    'artifact_recorded',
    'tests_discovered',
    'quality_run',
    'policy_evaluated',
    'subprocess_completed',
    'workspace_created',
    'task_finalized',
]
SECRET_RE = re.compile(r'sk-[A-Za-z0-9_-]{16,}|manual-elevate-test-key|x-api-key')


def run(cmd: list[str]) -> None:
    env = os.environ.copy()
    env['EVAL_TELEMETRY_ROOT'] = str(TELEMETRY_ROOT)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=180)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    print(proc.stdout.strip())


def main() -> int:
    if TELEMETRY_ROOT.exists():
        shutil.rmtree(TELEMETRY_ROOT)
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)

    run([sys.executable, 'scripts/manual/manual_elevate_smoke_endpoint_test.py'])
    run([sys.executable, 'scripts/manual/manual_elevate_core_endpoint_test.py'])

    if not EVENTS.exists():
        raise SystemExit(f'missing telemetry file: {EVENTS}')
    lines = EVENTS.read_text(encoding='utf-8').splitlines()
    counts: collections.Counter[str] = collections.Counter()
    secret_hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        event = json.loads(line)
        counts[str(event.get('event_type'))] += 1
        if SECRET_RE.search(line):
            secret_hits.append((i, line[:300]))
    missing = [name for name in REQUIRED_EVENTS if counts[name] == 0]
    report = {
        'events_path': str(EVENTS),
        'event_count': len(lines),
        'event_type_counts': dict(sorted(counts.items())),
        'required_events': REQUIRED_EVENTS,
        'missing_required_events': missing,
        'secret_hits': secret_hits[:5],
    }
    out = Path('/tmp/gpt-api-phase1-telemetry-report.json')
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({
        'report': str(out),
        'event_count': len(lines),
        'missing_required_events': missing,
        'secret_hit_count': len(secret_hits),
    }, indent=2))
    return 0 if not missing and not secret_hits else 1


if __name__ == '__main__':
    raise SystemExit(main())
