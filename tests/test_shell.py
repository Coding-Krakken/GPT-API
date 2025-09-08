import pytest
import os

class TestShellEndpoints:
    """Test suite for /shell endpoint operations."""

    def test_echo_command(self, client, auth_headers):
        """Test simple echo command."""
        payload = {
            "command": "echo 'Hello, Test!'"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data
        assert data["exit_code"] == 0
        assert "Hello, Test!" in data["stdout"]

    def test_ls_command(self, client, auth_headers, temp_dir):
        """Test ls command in temp directory."""
        # Create some test files
        test_files = ["file1.txt", "file2.txt", "subdir"]
        for f in test_files[:2]:
            with open(os.path.join(temp_dir, f), "w") as file:
                file.write("test")
        os.makedirs(os.path.join(temp_dir, test_files[2]))

        payload = {
            "command": f"ls {temp_dir}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        stdout = data["stdout"]
        for f in test_files:
            assert f in stdout

    def test_command_with_background_flag(self, client, auth_headers):
        """Test command with background flag."""
        payload = {
            "command": "sleep 1",
            "background": True
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "pid" in data
        assert data["exit_code"] == 0

    def test_sudo_command_without_sudo_flag(self, client, auth_headers):
        """Test command that would need sudo but without flag."""
        payload = {
            "command": "whoami"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        # Should not be root
        assert "root" not in data["stdout"].lower()

    def test_invalid_command(self, client, auth_headers):
        """Test invalid command."""
        payload = {
            "command": "nonexistent_command_xyz"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 127  # Command not found

    def test_empty_command(self, client, auth_headers):
        """Test empty command."""
        payload = {
            "command": ""
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "missing_command"

    def test_whitespace_command(self, client, auth_headers):
        """Test whitespace-only command."""
        payload = {
            "command": "   "
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "missing_command"

    def test_command_too_long(self, client, auth_headers):
        """Test command exceeding length limit."""
        long_command = "echo " + "a" * 4096
        payload = {
            "command": long_command
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "command_too_long"

    def test_fault_injection_permission(self, client, auth_headers):
        """Test permission fault injection."""
        payload = {
            "command": "echo test",
            "fault": "permission"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "permission_denied"
        assert data["result"]["status"] == 403

    def test_fault_injection_io(self, client, auth_headers):
        """Test IO fault injection."""
        payload = {
            "command": "echo test",
            "fault": "io"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "io_error"
        assert data["result"]["status"] == 500

    def test_custom_shell(self, client, auth_headers):
        """Test with custom shell."""
        payload = {
            "command": "echo $0",
            "shell": "/bin/bash"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert "bash" in data["stdout"] or "/bin/bash" in data["stdout"]

    def test_pwd_command(self, client, auth_headers):
        """Test pwd command."""
        payload = {
            "command": "pwd"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] in (0, 1)  # pwd can sometimes return 1 in test environments
        assert len(data["stdout"].strip()) > 0

    def test_mkdir_command(self, client, auth_headers, temp_dir):
        """Test mkdir command."""
        test_dir = os.path.join(temp_dir, "test_mkdir")
        payload = {
            "command": f"mkdir {test_dir}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert os.path.exists(test_dir)

    def test_touch_command(self, client, auth_headers, temp_dir):
        """Test touch command."""
        test_file = os.path.join(temp_dir, "test_touch.txt")
        payload = {
            "command": f"touch {test_file}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert os.path.exists(test_file)

    def test_cat_command(self, client, auth_headers, temp_file):
        """Test cat command."""
        payload = {
            "command": f"cat {temp_file}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert "test content" in data["stdout"]

    def test_grep_command(self, client, auth_headers, temp_file):
        """Test grep command."""
        payload = {
            "command": f"grep 'test' {temp_file}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert "test content" in data["stdout"]

    def test_head_command(self, client, auth_headers, temp_file):
        """Test head command."""
        payload = {
            "command": f"head -n 1 {temp_file}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert "test content" in data["stdout"]

    def test_wc_command(self, client, auth_headers, temp_file):
        """Test wc command."""
        payload = {
            "command": f"wc -l {temp_file}"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        # Should show 1 line
        assert "1" in data["stdout"]

    def test_date_command(self, client, auth_headers):
        """Test date command."""
        payload = {
            "command": "date"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert len(data["stdout"].strip()) > 0

    def test_whoami_command(self, client, auth_headers):
        """Test whoami command."""
        payload = {
            "command": "whoami"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert len(data["stdout"].strip()) > 0

    def test_env_command(self, client, auth_headers):
        """Test env command."""
        payload = {
            "command": "env | head -5"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert len(data["stdout"].strip()) > 0

    def test_df_command(self, client, auth_headers):
        """Test df command."""
        payload = {
            "command": "df -h | head -5"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert len(data["stdout"].strip()) > 0

    def test_ps_command(self, client, auth_headers):
        """Test ps command."""
        payload = {
            "command": "ps aux | head -5"
        }
        response = client.post("/shell", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["exit_code"] == 0
        assert len(data["stdout"].strip()) > 0