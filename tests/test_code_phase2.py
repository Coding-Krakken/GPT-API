from __future__ import annotations

import subprocess
from pathlib import Path


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CodeOps Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "codeops@example.com"], cwd=repo, check=True)
    (repo / "pytest.ini").write_text("[pytest]\npythonpath=.\n", encoding="utf-8")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "mathlib.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_mathlib.py").write_text("from pkg.mathlib import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    (repo / "tests" / "test_import_path.py").write_text("import pkg.mathlib\n\ndef test_import_path():\n    assert pkg.mathlib.add(2, 2) == 4\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_code_test_infers_python_for_pytest_file(client, auth_headers, tmp_path):
    repo = _repo(tmp_path)
    response = client.post("/code", headers=auth_headers, json={
        "action": "test",
        "path": str(repo / "tests" / "test_mathlib.py"),
        "working_dir": str(repo),
        "timeout_seconds": 60,
    })
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == 200, body
    assert body["result"]["language"] == "python"
    assert body["result"]["validationResult"]["status"] == "passed"


def test_code_test_repo_root_uses_working_dir_pythonpath(client, auth_headers, tmp_path):
    repo = _repo(tmp_path)
    response = client.post("/code", headers=auth_headers, json={
        "action": "test",
        "path": str(repo),
        "working_dir": str(repo),
        "timeout_seconds": 60,
    })
    body = response.json()
    assert body["status"] == 200, body
    assert body["result"]["validationResult"]["command"].startswith("pytest .")
    assert "2 passed" in body["result"]["stdout"]


def test_code_test_accepts_multi_file_pytest_argv(client, auth_headers, tmp_path):
    repo = _repo(tmp_path)
    response = client.post("/code", headers=auth_headers, json={
        "action": "test",
        "path": str(repo),
        "working_dir": str(repo),
        "language": "python",
        "argv": ["pytest", "-q", "tests/test_mathlib.py", "tests/test_import_path.py"],
        "timeout_seconds": 60,
    })
    body = response.json()
    assert body["status"] == 200, body
    assert body["result"]["validationResult"]["status"] == "passed"
    assert "tests/test_mathlib.py" in body["result"]["validationResult"]["command"]


def test_code_test_accepts_safe_pytest_args_selectors(client, auth_headers, tmp_path):
    repo = _repo(tmp_path)
    response = client.post("/code", headers=auth_headers, json={
        "action": "test",
        "path": str(repo),
        "working_dir": str(repo),
        "args": "-q tests/test_mathlib.py tests/test_import_path.py",
        "timeout_seconds": 60,
    })
    body = response.json()
    assert body["status"] == 200, body
    assert body["result"]["validationResult"]["status"] == "passed"


def test_code_test_rejects_unsafe_pytest_argv(client, auth_headers, tmp_path):
    repo = _repo(tmp_path)
    response = client.post("/code", headers=auth_headers, json={
        "action": "test",
        "path": str(repo),
        "working_dir": str(repo),
        "argv": ["pytest", "-q", "tests/test_mathlib.py;rm -rf /"],
    })
    body = response.json()
    assert body["result"]["error"]["code"] == "invalid_args"
