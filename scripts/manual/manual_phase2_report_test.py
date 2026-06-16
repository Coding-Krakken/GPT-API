from __future__ import annotations

import sys
from pathlib import Path as _ManualPath

REPO_ROOT = _ManualPath(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = REPO_ROOT
TELEMETRY_ROOT = Path('/tmp/gpt-api-phase2-report-test')
EVENTS = TELEMETRY_ROOT / 'events.jsonl'


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['EVAL_TELEMETRY_ROOT'] = str(TELEMETRY_ROOT)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=240)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc


def main() -> int:
    if TELEMETRY_ROOT.exists():
        shutil.rmtree(TELEMETRY_ROOT)
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)

    run([sys.executable, 'scripts/manual/manual_elevate_smoke_endpoint_test.py'])
    assert EVENTS.exists(), f'missing telemetry: {EVENTS}'

    proc = run([sys.executable, '-m', 'evals.report', '--events', str(EVENTS), '--report-id', 'phase2_manual_report'])
    summary = json.loads(proc.stdout)
    report_json = Path(summary['report_json'])
    report_md = Path(summary['report_md'])
    assert report_json.exists(), report_json
    assert report_md.exists(), report_md

    report = json.loads(report_json.read_text(encoding='utf-8'))
    md = report_md.read_text(encoding='utf-8')
    assert report['summary']['event_count'] > 0
    assert report['scores']['agent']['score'] >= 0
    assert report['scores']['backend']['score'] >= 0
    assert 'endpoint_stats' in report
    assert 'recommendations' in report and report['recommendations']
    assert 'Coding GPT Evaluation Report' in md
    assert 'Agent score' in md
    assert 'Backend score' in md
    assert 'Recommendations' in md
    assert 'Event type counts' in md

    out = {
        'events': str(EVENTS),
        'event_count': report['summary']['event_count'],
        'agent_score': report['scores']['agent']['score'],
        'backend_score': report['scores']['backend']['score'],
        'report_json': str(report_json),
        'report_md': str(report_md),
        'failure_count': len(report.get('failures', [])),
        'recommendation_count': len(report.get('recommendations', [])),
    }
    Path('/tmp/gpt-api-phase2-report-summary.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
