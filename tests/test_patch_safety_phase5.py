import subprocess
from pathlib import Path

import pytest

from utils.policy import PolicyError
from utils import patching


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Patch Safety"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "patch-safety@example.com"], cwd=path, check=True)
    (path / "app.py").write_text("def value():\n    return 'safe'\n", encoding="utf-8")
    (path / "README.md").write_text("safe readme\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _workspace(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    return repo


def test_patch_preview_rejects_editor_patch_blocks_without_mutating(client, auth_headers, tmp_path, monkeypatch):
    repo = _workspace(tmp_path, monkeypatch)
    original = (repo / "app.py").read_text(encoding="utf-8")
    editor_patch = """*** Begin Patch
*** Update File: app.py
@@
-def value():
-    return 'safe'
+def value():
+    return 'changed'
*** End Patch
"""

    body = client.post(
        "/patch/preview",
        headers=auth_headers,
        json={"workspace_path": str(repo), "patch": editor_patch},
    ).json()

    assert body["status"] == 400
    assert body["error"]["code"] == "invalid_unified_diff"
    assert "details" in body["error"]
    assert (repo / "app.py").read_text(encoding="utf-8") == original


def test_patch_apply_rejects_malformed_patch_without_mutating(client, auth_headers, tmp_path, monkeypatch):
    repo = _workspace(tmp_path, monkeypatch)
    original = (repo / "README.md").read_text(encoding="utf-8")
    malformed = """diff --git a/README.md b/README.md
@@ -1 +1 @@
-safe readme
+corrupted
"""

    body = client.post(
        "/patch/apply",
        headers=auth_headers,
        json={"workspace_path": str(repo), "patch": malformed},
    ).json()

    assert body["status"] == 400
    assert body["error"]["code"] == "invalid_unified_diff"
    assert (repo / "README.md").read_text(encoding="utf-8") == original
    assert "*** Begin Patch" not in (repo / "README.md").read_text(encoding="utf-8")


def test_patch_preview_and_apply_block_secret_like_paths(client, auth_headers, tmp_path, monkeypatch):
    repo = _workspace(tmp_path, monkeypatch)
    blocked_patches = [
        "diff --git a/.env.local b/.env.local\nnew file mode 100644\n--- /dev/null\n+++ b/.env.local\n@@ -0,0 +1 @@\n+API_KEY=x\n",
        "diff --git a/config/secret-token.txt b/config/secret-token.txt\nnew file mode 100644\n--- /dev/null\n+++ b/config/secret-token.txt\n@@ -0,0 +1 @@\n+token=x\n",
        "diff --git a/certs/client.p12 b/certs/client.p12\nnew file mode 100644\n--- /dev/null\n+++ b/certs/client.p12\n@@ -0,0 +1 @@\n+binary-ish\n",
        "diff --git a/../escape.txt b/../escape.txt\n--- a/../escape.txt\n+++ b/../escape.txt\n@@ -1 +1 @@\n-old\n+new\n",
    ]

    for patch in blocked_patches:
        preview = client.post(
            "/patch/preview",
            headers=auth_headers,
            json={"workspace_path": str(repo), "patch": patch},
        ).json()
        apply = client.post(
            "/patch/apply",
            headers=auth_headers,
            json={"workspace_path": str(repo), "patch": patch},
        ).json()
        assert preview["status"] == 400
        assert apply["status"] == 400
        assert preview["error"]["code"] in {"blocked_patch_path", "path_traversal_forbidden"}
        assert apply["error"]["code"] == preview["error"]["code"]

    assert not (repo / ".env.local").exists()
    assert not (repo / "config").exists()
    assert not (repo.parent / "escape.txt").exists()


def test_patch_preview_and_apply_have_same_touched_files_for_safe_patch(client, auth_headers, tmp_path, monkeypatch):
    repo = _workspace(tmp_path, monkeypatch)
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def value():
-    return 'safe'
+    return 'safer'
"""

    preview = client.post(
        "/patch/preview",
        headers=auth_headers,
        json={"workspace_path": str(repo), "patch": patch},
    ).json()
    apply = client.post(
        "/patch/apply",
        headers=auth_headers,
        json={"workspace_path": str(repo), "patch": patch},
    ).json()

    assert preview["status"] == 200
    assert apply["status"] == 200
    assert preview["applies"] is True
    assert apply["applied"] is True
    assert preview["files_touched"] == apply["files_touched"] == ["app.py"]
    assert "safer" in (repo / "app.py").read_text(encoding="utf-8")


def test_touched_files_rejects_diff_header_without_file_headers():
    with pytest.raises(PolicyError) as exc:
        patching.touched_files("diff --git a/app.py b/app.py\n@@ -1 +1 @@\n-a\n+b\n")
    assert exc.value.code == "invalid_unified_diff"
