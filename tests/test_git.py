import pytest
import os
import subprocess

class TestGitEndpoints:
    """Test suite for /git endpoint operations."""

    def test_git_init(self, client, auth_headers, temp_dir):
        """Test git init."""
        payload = {
            "action": "init",
            "path": temp_dir
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0
        # Verify .git directory was created
        assert os.path.exists(os.path.join(temp_dir, ".git"))

    def test_git_status(self, client, auth_headers, temp_git_repo):
        """Test git status."""
        payload = {
            "action": "status",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0
        assert "stdout" in data

    def test_git_add(self, client, auth_headers, temp_git_repo):
        """Test git add."""
        # Create a new file
        new_file = os.path.join(temp_git_repo, "new_file.txt")
        with open(new_file, "w") as f:
            f.write("new content")

        payload = {
            "action": "add",
            "path": temp_git_repo,
            "args": "new_file.txt"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_commit(self, client, auth_headers, temp_git_repo):
        """Test git commit."""
        # First add a file
        new_file = os.path.join(temp_git_repo, "commit_file.txt")
        with open(new_file, "w") as f:
            f.write("commit content")

        # Add the file
        subprocess.run(["git", "-C", temp_git_repo, "add", "commit_file.txt"], check=True)

        payload = {
            "action": "commit",
            "path": temp_git_repo,
            "args": "-m 'Test commit'"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_log(self, client, auth_headers, temp_git_repo):
        """Test git log."""
        payload = {
            "action": "log",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0
        assert "Initial commit" in data["stdout"]

    def test_git_diff(self, client, auth_headers, temp_git_repo):
        """Test git diff."""
        # Modify existing file
        existing_file = os.path.join(temp_git_repo, "test.txt")
        with open(existing_file, "a") as f:
            f.write("\nmodified content")

        payload = {
            "action": "diff",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_checkout_new_branch(self, client, auth_headers, temp_git_repo):
        """Test git checkout new branch."""
        payload = {
            "action": "checkout",
            "path": temp_git_repo,
            "args": "-b new_branch"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_branch(self, client, auth_headers, temp_git_repo):
        """Test git branch."""
        payload = {
            "action": "branch",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0
        assert "main" in data["stdout"] or "master" in data["stdout"]

    def test_git_config(self, client, auth_headers, temp_git_repo):
        """Test git config."""
        payload = {
            "action": "config",
            "path": temp_git_repo,
            "args": "--list"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_invalid_action(self, client, auth_headers, temp_git_repo):
        """Test invalid git action."""
        payload = {
            "action": "invalid_action",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_action"

    def test_git_missing_path(self, client, auth_headers):
        """Test missing path."""
        payload = {
            "action": "status"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_path"

    def test_git_nonexistent_path(self, client, auth_headers, temp_dir):
        """Test nonexistent path."""
        nonexistent_path = os.path.join(temp_dir, "nonexistent")
        payload = {
            "action": "status",
            "path": nonexistent_path
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_path"
        assert data["status"] == 400

    def test_git_init_on_existing_repo(self, client, auth_headers, temp_git_repo):
        """Test git init on existing repo."""
        payload = {
            "action": "init",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        # Should still succeed even if already initialized

    def test_git_status_with_debug(self, client, auth_headers, temp_git_repo):
        """Test git status with debug flag."""
        payload = {
            "action": "status",
            "path": temp_git_repo,
            "debug": True
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert "debug" in data

    def test_git_commit_without_identity(self, client, auth_headers, temp_dir):
        """Test git commit without user identity."""
        # Create a new repo without identity
        new_repo = os.path.join(temp_dir, "no_identity")
        os.makedirs(new_repo)
        subprocess.run(["git", "init"], cwd=new_repo, check=True)

        # Create and add a file
        test_file = os.path.join(new_repo, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        subprocess.run(["git", "add", "test.txt"], cwd=new_repo, check=True)

        # Remove git config more thoroughly
        subprocess.run(["git", "config", "--unset", "user.name"], cwd=new_repo)
        subprocess.run(["git", "config", "--unset", "user.email"], cwd=new_repo)
        # Also remove global config to be sure
        subprocess.run(["git", "config", "--global", "--unset", "user.name"], cwd=new_repo)
        subprocess.run(["git", "config", "--global", "--unset", "user.email"], cwd=new_repo)

        payload = {
            "action": "commit",
            "path": new_repo,
            "args": "-m 'Test commit'"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "missing_identity"
        assert data["status"] == 400

    def test_git_clone(self, client, auth_headers, temp_dir):
        """Test git clone (using local repo as source)."""
        # Create a bare repo to clone from and add a commit
        source_repo = os.path.join(temp_dir, "source.git")
        os.makedirs(source_repo)
        subprocess.run(["git", "init", "--bare"], cwd=source_repo, check=True)
        
        # Create a temp repo with a commit to push to the bare repo
        temp_repo = os.path.join(temp_dir, "temp")
        os.makedirs(temp_repo)
        subprocess.run(["git", "init"], cwd=temp_repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_repo)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_repo)
        
        # Create and commit a file
        test_file = os.path.join(temp_repo, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        subprocess.run(["git", "add", "test.txt"], cwd=temp_repo)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_repo)
        
        # Push to bare repo
        subprocess.run(["git", "remote", "add", "origin", source_repo], cwd=temp_repo)
        subprocess.run(["git", "push", "origin", "master"], cwd=temp_repo)

        # Clone it
        dest_repo = os.path.join(temp_dir, "cloned")
        payload = {
            "action": "clone",
            "path": dest_repo,
            "args": source_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0
        assert os.path.exists(os.path.join(dest_repo, ".git"))

    def test_git_reset(self, client, auth_headers, temp_git_repo):
        """Test git reset."""
        payload = {
            "action": "reset",
            "path": temp_git_repo,
            "args": "--hard HEAD"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_remote(self, client, auth_headers, temp_git_repo):
        """Test git remote."""
        payload = {
            "action": "remote",
            "path": temp_git_repo,
            "args": "-v"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0

    def test_git_fetch(self, client, auth_headers, temp_git_repo):
        """Test git fetch."""
        payload = {
            "action": "fetch",
            "path": temp_git_repo
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        # Exit code might be non-zero if no remote, but that's okay

    def test_git_rebase(self, client, auth_headers, temp_git_repo):
        """Test git rebase."""
        payload = {
            "action": "rebase",
            "path": temp_git_repo,
            "args": "--continue"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        # Rebase --continue fails when no rebase is in progress, so we expect an error
        assert data["exit_code"] != 0  # Command failed
        assert data["status"] == 400  # Git error status

    def test_git_tag(self, client, auth_headers, temp_git_repo):
        """Test git tag."""
        payload = {
            "action": "tag",
            "path": temp_git_repo,
            "args": "v1.0"
        }
        response = client.post("/git", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["exit_code"] == 0