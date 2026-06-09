import subprocess
from pathlib import Path


def _init_repo(path: Path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    (path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (path / "tests").mkdir()
    (path / "tests" / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_coding_key_cannot_call_operator_routes(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "operator-key")
    monkeypatch.setenv("OPERATOR_GPT_API_KEY", "operator-key")
    monkeypatch.setenv("CODING_GPT_API_KEY", "coding-key")
    headers = {"x-api-key": "coding-key"}
    for path, payload in [
        ("/shell/", {"command": "echo nope"}),
        ("/files/", {"action": "list", "path": "."}),
        ("/package/", {"manager": "pip", "action": "list"}),
        ("/apps/", {"action": "list"}),
        ("/gpts/", {"name": "x", "description": "x", "instructions": "x"}),
    ]:
        resp = client.post(path, headers=headers, json=payload)
        assert resp.status_code == 403


def test_openai_gpt_id_header_does_not_bypass_auth(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "operator-key")
    resp = client.post(
        "/shell/",
        headers={"openai-gpt-id": "g-test"},
        json={"command": "echo unsafe"},
    )
    assert resp.status_code == 403


def test_blocked_patch_path_is_rejected(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("WORKTREE_ROOT", str(tmp_path / "worktrees"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    ws = Path(
        client.post(
            "/workspace/create",
            headers=auth_headers,
            json={"repo_path": str(repo), "task_id": "blocked"},
        ).json()["workspace_path"]
    )
    patch = """diff --git a/.env b/.env
new file mode 100644
--- /dev/null
+++ b/.env
@@ -0,0 +1 @@
+API_KEY=secret
"""
    body = client.post(
        "/patch/preview",
        headers=auth_headers,
        json={"workspace_path": str(ws), "patch": patch},
    ).json()
    assert body["status"] == 400
    assert body["error"]["code"] == "blocked_patch_path"


def test_dirty_workspace_destroy_requires_force(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("WORKTREE_ROOT", str(tmp_path / "worktrees"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    ws = Path(
        client.post(
            "/workspace/create",
            headers=auth_headers,
            json={"repo_path": str(repo), "task_id": "dirty"},
        ).json()["workspace_path"]
    )
    (ws / "app.py").write_text(
        "def add(a, b):\n    return int(a) + int(b)\n",
        encoding="utf-8",
    )
    body = client.post(
        "/workspace/destroy",
        headers=auth_headers,
        json={"workspace_path": str(ws)},
    ).json()
    assert body["status"] == 400
    assert body["error"]["code"] == "dirty_workspace"


def test_workspace_commit_and_pr_dry_run(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("WORKTREE_ROOT", str(tmp_path / "worktrees"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    ws = Path(
        client.post(
            "/workspace/create",
            headers=auth_headers,
            json={"repo_path": str(repo), "task_id": "commit"},
        ).json()["workspace_path"]
    )
    (ws / "app.py").write_text(
        "def add(a, b):\n    return int(a) + int(b)\n",
        encoding="utf-8",
    )
    commit = client.post(
        "/workspace/commit",
        headers=auth_headers,
        json={"workspace_path": str(ws), "message": "safe coding change"},
    ).json()
    assert commit["committed"] is True
    pr = client.post(
        "/workspace/pr-create",
        headers=auth_headers,
        json={"workspace_path": str(ws), "title": "Safe coding change", "body": "Test body"},
    ).json()
    assert pr["dry_run"] is True
    assert pr["argv"][:3] == ["gh", "pr", "create"]
