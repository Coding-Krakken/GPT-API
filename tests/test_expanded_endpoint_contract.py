import json
import os
import time
import subprocess
from pathlib import Path


def test_shell_expanded_controls(client, auth_headers, temp_dir):
    resp = client.post('/shell', headers=auth_headers, json={
        'command': 'cat',
        'working_dir': temp_dir,
        'env': {'EXPANDED_TEST_VAR': 'ok'},
        'stdin': 'hello stdin',
        'allowed_exit_codes': [0],
    }).json()
    assert resp['exit_code'] == 0
    assert resp['stdout'] == 'hello stdin'

    dry = client.post('/shell', headers=auth_headers, json={'command': 'echo dry', 'dry_run': True}).json()
    assert dry['dry_run'] is True
    assert 'echo dry' in dry['command']

    allowed = client.post('/shell', headers=auth_headers, json={'command': 'exit 7', 'allowed_exit_codes': [7]}).json()
    assert allowed['exit_code'] == 7
    assert allowed['status'] == 200

    truncated = client.post('/shell', headers=auth_headers, json={
        'command': "python -c \"print('x'*5000)\"",
        'max_output_bytes': 1024,
    }).json()
    assert 'output truncated' in truncated['stdout']


def test_shell_background_job_lifecycle(client, auth_headers):
    start = client.post('/shell', headers=auth_headers, json={
        'action': 'start',
        'command': 'sleep 5',
    }).json()
    assert start['job_id']
    job_id = start['job_id']
    status = client.post('/shell', headers=auth_headers, json={'action': 'status', 'job_id': job_id}).json()
    assert status['job_id'] == job_id
    assert 'running' in status
    stopped = client.post('/shell', headers=auth_headers, json={'action': 'stop', 'job_id': job_id}).json()
    assert stopped['job_id'] == job_id
    assert stopped['running'] is False


def test_files_expanded_editing_discovery_and_snapshots(client, auth_headers, temp_dir):
    base = Path(temp_dir) / 'file.txt'
    base.write_text('line1\nline2\nline3\n', encoding='utf-8')

    checksum = client.post('/files', headers=auth_headers, json={'action': 'checksum', 'path': str(base)}).json()['result']['sha256']
    mismatch = client.post('/files', headers=auth_headers, json={
        'action': 'write', 'path': str(base), 'content': 'bad', 'expected_hash': 'not-the-hash'
    }).json()['result']
    assert mismatch['error']['code'] == 'hash_mismatch'

    append = client.post('/files', headers=auth_headers, json={'action': 'append', 'path': str(base), 'content': 'tail\n'}).json()['result']
    assert append['status'] == 200
    prepend = client.post('/files', headers=auth_headers, json={'action': 'prepend', 'path': str(base), 'content': 'head\n'}).json()['result']
    assert prepend['status'] == 200
    assert base.read_text(encoding='utf-8').startswith('head\n')

    replace = client.post('/files', headers=auth_headers, json={
        'action': 'replace_range', 'path': str(base), 'range': {'start_line': 2, 'end_line': 2}, 'content': 'REPLACED\n'
    }).json()['result']
    assert replace['status'] == 200
    assert 'REPLACED' in base.read_text(encoding='utf-8')

    insert = client.post('/files', headers=auth_headers, json={
        'action': 'insert_after', 'path': str(base), 'range': {'start_line': 1}, 'content': 'AFTER\n'
    }).json()['result']
    assert insert['status'] == 200

    delete = client.post('/files', headers=auth_headers, json={
        'action': 'delete_range', 'path': str(base), 'range': {'start_line': 1, 'end_line': 1}
    }).json()['result']
    assert delete['status'] == 200

    backup = client.post('/files', headers=auth_headers, json={
        'action': 'write', 'path': str(base), 'content': 'new\n', 'backup': True, 'expected_hash': client.post('/files', headers=auth_headers, json={'action': 'checksum', 'path': str(base)}).json()['result']['sha256']
    }).json()['result']
    assert backup['backup_path'] and Path(backup['backup_path']).exists()

    snap_path = str(Path(temp_dir) / 'snap.txt')
    snap = client.post('/files', headers=auth_headers, json={'action': 'snapshot', 'path': str(base), 'target_path': snap_path}).json()['result']
    assert snap['status'] == 200
    base.write_text('mutated', encoding='utf-8')
    restore = client.post('/files', headers=auth_headers, json={'action': 'restore', 'path': snap_path, 'target_path': str(base)}).json()['result']
    assert restore['status'] == 200
    assert base.read_text(encoding='utf-8') == 'new\n'

    globbed = client.post('/files', headers=auth_headers, json={'action': 'glob', 'path': str(Path(temp_dir) / '*.txt')}).json()['result']
    assert str(base) in globbed['matches']
    tree = client.post('/files', headers=auth_headers, json={'action': 'tree', 'path': temp_dir, 'max_depth': 2}).json()['result']
    assert any(item['relative_path'] == 'file.txt' for item in tree['items'])


def test_code_expanded_actions_and_metadata(client, auth_headers, temp_dir):
    py = Path(temp_dir) / 'sample.py'
    py.write_text('import os, sys\nprint(os.getenv("EXPANDED_CODE_VAR"))\nprint(sys.stdin.read())\n', encoding='utf-8')

    run = client.post('/code', headers=auth_headers, json={
        'action': 'run', 'path': str(py), 'language': 'python', 'env': {'EXPANDED_CODE_VAR': 'yes'}, 'stdin': 'input-data'
    }).json()['result']
    assert run['exit_code'] == 0
    assert 'yes' in run['stdout']
    assert 'input-data' in run['stdout']

    dry = client.post('/code', headers=auth_headers, json={'action': 'run', 'path': str(py), 'language': 'python', 'dry_run': True}).json()['result']
    assert dry['exit_code'] == 0
    assert 'python' in dry['stdout']

    chained = client.post('/code', headers=auth_headers, json={'actions': ['compile', 'run'], 'path': str(py), 'language': 'python'}).json()
    assert chained['chained'] is True
    assert len(chained['results']) == 2

    risky = Path(temp_dir) / 'risky.py'
    risky.write_text('eval("1+1")\n', encoding='utf-8')
    static = client.post('/code', headers=auth_headers, json={'action': 'static_analyze', 'path': str(risky), 'language': 'python'}).json()
    assert static['diagnostics']
    assert any('eval' in d['message'] for d in static['diagnostics'])

    sec_file = Path(temp_dir) / 'sec.py'
    sec_file.write_text('password="secret"\n', encoding='utf-8')
    scan = client.post('/code', headers=auth_headers, json={'action': 'security_scan', 'path': str(sec_file), 'language': 'python'}).json()
    assert scan['diagnostics']

    summary = client.post('/code', headers=auth_headers, json={'action': 'summarize', 'path': str(py), 'language': 'python'}).json()['result']
    assert 'summary' in summary
    tests = client.post('/code', headers=auth_headers, json={'action': 'generate_tests', 'path': str(py), 'language': 'python'}).json()
    assert tests['artifacts'][0]['type'] == 'test_suggestion'


def test_git_expanded_typed_actions(client, auth_headers, temp_git_repo):
    repo = Path(temp_git_repo)
    target = repo / 'test.txt'
    target.write_text('changed\n', encoding='utf-8')

    diff = client.post('/git', headers=auth_headers, json={'action': 'diff', 'path': str(repo), 'files': ['test.txt']}).json()
    assert diff['exit_code'] == 0
    assert 'changed' in diff['diff']

    dry_add = client.post('/git', headers=auth_headers, json={'action': 'add', 'path': str(repo), 'files': ['test.txt'], 'dry_run': True}).json()
    assert dry_add['dry_run'] is True
    assert 'git' in dry_add['stdout']

    patch = 'diff --git a/newfile.txt b/newfile.txt\nnew file mode 100644\nindex 0000000..3b18e51\n--- /dev/null\n+++ b/newfile.txt\n@@ -0,0 +1 @@\n+hello\n'
    applied = client.post('/git', headers=auth_headers, json={'action': 'apply_patch', 'path': str(repo), 'patch': patch, 'dry_run': True}).json()
    assert applied['exit_code'] == 0

    summary = client.post('/git', headers=auth_headers, json={'action': 'create_pr_summary', 'path': str(repo), 'base': 'HEAD'}).json()
    assert 'summary' in summary
    assert 'Diff against HEAD' in summary['summary']

    branch = client.post('/git', headers=auth_headers, json={'action': 'branch', 'path': str(repo), 'branch': 'expanded-test'}).json()
    assert branch['exit_code'] == 0


def test_package_expanded_dry_run_fields(client, auth_headers, temp_dir):
    dry = client.post('/package', headers=auth_headers, json={
        'manager': 'pip', 'action': 'install', 'packages': ['example-pkg'], 'version': '1.2.3', 'dry_run': True, 'working_dir': temp_dir
    }).json()
    assert dry['dry_run'] is True
    assert 'example-pkg==1.2.3' in dry['stdout']

    freeze = client.post('/package', headers=auth_headers, json={'manager': 'pip', 'action': 'freeze', 'dry_run': True}).json()
    assert freeze['dry_run'] is True
    assert 'pip freeze' in freeze['stdout']

    bad_dir = client.post('/package', headers=auth_headers, json={
        'manager': 'pip', 'action': 'list', 'working_dir': str(Path(temp_dir) / 'missing')
    }).json()
    assert bad_dir['error']['code'] == 'invalid_working_dir'


def test_refactor_expanded_modes_scope_preview_and_backup(client, auth_headers, temp_dir):
    one = Path(temp_dir) / 'one.py'
    two = Path(temp_dir) / 'two.py'
    skip = Path(temp_dir) / 'skip.txt'
    one.write_text('import sys\nimport os\n\nvalue_1 = 1\nvalue_2 = 2\nname = value_1\n', encoding='utf-8')
    two.write_text('value_3 = 3\n', encoding='utf-8')
    skip.write_text('value_4 = 4\n', encoding='utf-8')

    preview = client.post('/refactor', headers=auth_headers, json={
        'mode': 'regex', 'search': r'value_(\d)', 'replace': r'item_\1', 'files': [str(one)], 'preview': True
    }).json()
    assert preview['dry_run'] is True
    assert 'item_1' not in one.read_text(encoding='utf-8')

    applied = client.post('/refactor', headers=auth_headers, json={
        'mode': 'symbol', 'symbol': 'value_1', 'new_name': 'renamed_value', 'search': 'value_1', 'replace': 'renamed_value', 'files': [str(one)], 'backup': True
    }).json()
    assert applied['changed_files'] == [str(one)]
    assert 'renamed_value' in one.read_text(encoding='utf-8')
    assert list(Path(temp_dir).glob('one.py.bak.*'))

    scoped = client.post('/refactor', headers=auth_headers, json={
        'search': 'value_', 'replace': 'scoped_', 'scope': {'root': temp_dir, 'include': ['*.py'], 'exclude': ['two.py']}, 'files': None, 'preview': True
    }).json()
    assert str(one) in scoped['changed_files']
    assert str(two) not in scoped['changed_files']
    assert str(skip) not in scoped['changed_files']

    organized = client.post('/refactor', headers=auth_headers, json={
        'mode': 'organize_imports', 'search': '', 'replace': '', 'files': [str(one)]
    }).json()
    assert organized['result'][0]['changed'] is True
    assert one.read_text(encoding='utf-8').splitlines()[0] == 'import os'


def test_batch_expanded_endpoint_payload_dependencies_and_modes(client, auth_headers, temp_dir):
    target = Path(temp_dir) / 'batch.txt'
    payload = {
        'mode': 'sequential',
        'operations': [
            {'id': 'write', 'endpoint': 'files', 'action': 'files', 'payload': {'action': 'write', 'path': str(target), 'content': 'alpha'}},
            {'id': 'read', 'endpoint': 'files', 'action': 'files', 'depends_on': ['write'], 'payload': {'action': 'read', 'path': str(target)}},
        ],
    }
    result = client.post('/batch', headers=auth_headers, json=payload).json()
    assert result['ok'] is True
    assert result['results'][1]['result']['content'] == 'alpha'

    dry = client.post('/batch', headers=auth_headers, json={'mode': 'dry_run', 'operations': payload['operations']}).json()
    assert dry['ok'] is True
    assert all(item['dry_run'] for item in dry['results'])

    parallel = client.post('/batch', headers=auth_headers, json={
        'mode': 'parallel',
        'operations': [
            {'id': 'a', 'endpoint': 'shell', 'action': 'shell', 'payload': {'command': 'echo A'}},
            {'id': 'b', 'endpoint': 'shell', 'action': 'shell', 'payload': {'command': 'echo B'}},
        ],
    }).json()
    assert parallel['ok'] is True
    assert len(parallel['results']) == 2

    rollback_file = Path(temp_dir) / 'rollback.txt'
    txn = client.post('/batch', headers=auth_headers, json={
        'mode': 'transaction', 'rollback_on_error': True,
        'operations': [
            {'id': 'write', 'endpoint': 'files', 'action': 'files', 'payload': {'action': 'write', 'path': str(rollback_file), 'content': 'created'}, 'rollback': {'endpoint': 'files', 'action': 'files', 'payload': {'action': 'delete', 'path': str(rollback_file)}}},
            {'id': 'fail', 'endpoint': 'files', 'action': 'files', 'payload': {'action': 'read', 'path': str(Path(temp_dir) / 'missing.txt')}},
        ],
    }).json()
    assert txn['ok'] is False
    assert txn['rollback_results']
    assert not rollback_file.exists()


def test_monitor_expanded_types(client, auth_headers, temp_git_repo, temp_dir):
    proc = client.post('/monitor', headers=auth_headers, json={'type': 'process', 'tail': 5}).json()
    assert 'metrics' in proc
    assert 'processes' in proc['metrics']

    ports = client.post('/monitor', headers=auth_headers, json={'type': 'ports', 'tail': 5}).json()
    assert 'connections' in ports['metrics']

    log_file = Path(temp_dir) / 'app.log'
    log_file.write_text('first\nneedle second\n', encoding='utf-8')
    logs = client.post('/monitor', headers=auth_headers, json={'type': 'logs', 'path': str(log_file), 'filter': 'needle'}).json()
    assert logs['logs'] == ['needle second']

    git = client.post('/monitor', headers=auth_headers, json={'type': 'git', 'path': temp_git_repo}).json()
    assert git['metrics']['path'] == str(Path(temp_git_repo))
    assert 'status_short' in git['metrics']

    tests = client.post('/monitor', headers=auth_headers, json={'type': 'tests', 'path': temp_dir}).json()
    assert 'collected_output' in tests['metrics']


def test_system_expanded_capability_report(client, auth_headers):
    data = client.get('/system', headers=auth_headers).json()
    for key in ['arch', 'cwd', 'shells', 'python', 'git', 'package_managers', 'tools', 'workspace_root', 'limits']:
        assert key in data
    assert isinstance(data['tools'], dict)
    assert data['limits']['max_timeout_seconds'] >= 300
