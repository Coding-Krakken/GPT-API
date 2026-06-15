import os
import subprocess
from pathlib import Path


def _init_repo(path: Path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    (path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (path / "tests").mkdir()
    (path / "tests" / "test_app.py").write_text("from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_repo_overview_search_read_symbols(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    resp = client.post("/repo/overview", headers=auth_headers, json={"repo_path": str(repo)})
    data = resp.json()
    assert data["status"] == 200
    assert data["is_git_repo"] is True
    assert "python" in data["languages"]

    resp = client.post("/repo/search", headers=auth_headers, json={"repo_path": str(repo), "query": "def add"})
    assert resp.json()["results"][0]["file"] == "app.py"

    resp = client.post("/repo/read-context", headers=auth_headers, json={"repo_path": str(repo), "files": ["app.py"]})
    assert "def add" in resp.json()["files"][0]["content"]

    resp = client.post("/repo/symbols", headers=auth_headers, json={"repo_path": str(repo), "files": ["app.py"]})
    symbols = resp.json()["files"][0]["symbols"]
    assert any(s["name"] == "add" for s in symbols)


def test_policy_blocks_secret_context(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("API_KEY=secret", encoding="utf-8")
    resp = client.post("/repo/read-context", headers=auth_headers, json={"repo_path": str(repo), "files": [".env"]})
    body = resp.json()
    assert body["status"] == 400
    assert body["error"]["code"] == "blocked_path"


def test_workspace_patch_test_quality_flow(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("WORKTREE_ROOT", str(tmp_path / "worktrees"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    resp = client.post("/workspace/create", headers=auth_headers, json={"repo_path": str(repo), "task_id": "change-add"})
    ws = Path(resp.json()["workspace_path"])
    assert ws.exists()

    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return int(a) + int(b)
"""
    resp = client.post("/patch/preview", headers=auth_headers, json={"workspace_path": str(ws), "patch": patch})
    assert resp.json()["applies"] is True
    resp = client.post("/patch/apply", headers=auth_headers, json={"workspace_path": str(ws), "patch": patch})
    assert resp.json()["applied"] is True

    resp = client.post("/test/discover", headers=auth_headers, json={"workspace_path": str(ws)})
    assert any(c["name"] == "pytest" for c in resp.json()["commands"])
    resp = client.post("/test/run", headers=auth_headers, json={"workspace_path": str(ws), "command_name": "pytest", "timeout_seconds": 60})
    assert resp.json()["passed"] is True

    resp = client.post("/quality/check", headers=auth_headers, json={"workspace_path": str(ws), "timeout_seconds": 60})
    assert resp.json()["passed"] is True

    resp = client.post("/workspace/diff", headers=auth_headers, json={"workspace_path": str(ws)})
    assert "int(a)" in resp.json()["diff"]


def test_coding_task_initializes_worktree(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("WORKTREE_ROOT", str(tmp_path / "worktrees"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    resp = client.post("/agent/coding-task", headers=auth_headers, json={"repo_path": str(repo), "task": "make a safe change"})
    body = resp.json()
    assert body["status"] == "workspace_ready"
    assert Path(body["workspace"]["workspace_path"]).exists()
    assert "patch" in body["message"].lower()
