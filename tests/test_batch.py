import pytest
import os

class TestBatchEndpoints:
    """Test suite for /batch endpoint operations."""

    def test_batch_shell_commands(self, client, auth_headers):
        """Test batch shell commands."""
        payload = {
            "operations": [
                {"action": "shell", "args": {"command": "echo 'first command'"}},
                {"action": "shell", "args": {"command": "echo 'second command'"}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["action"] == "shell"
        assert data["results"][1]["action"] == "shell"
        assert "first command" in data["results"][0]["stdout"]
        assert "second command" in data["results"][1]["stdout"]
        assert data["results"][0]["status"] == 200
        assert data["results"][1]["status"] == 200

    def test_batch_files_operations(self, client, auth_headers, temp_dir):
        """Test batch file operations."""
        file1 = os.path.join(temp_dir, "batch_file1.txt")
        file2 = os.path.join(temp_dir, "batch_file2.txt")

        payload = {
            "operations": [
                {"action": "files", "args": {"action": "write", "path": file1, "content": "content1"}},
                {"action": "files", "args": {"action": "write", "path": file2, "content": "content2"}},
                {"action": "files", "args": {"action": "read", "path": file1}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3
        # Check write operations
        assert data["results"][0]["action"] == "files"
        assert data["results"][1]["action"] == "files"
        # Check read operation
        assert data["results"][2]["action"] == "files"
        assert data["results"][2]["result"]["content"] == "content1"
        # Verify files were created
        assert os.path.exists(file1)
        assert os.path.exists(file2)

    def test_batch_mixed_operations(self, client, auth_headers, temp_dir):
        """Test batch with mixed operation types."""
        test_file = os.path.join(temp_dir, "mixed_test.txt")

        payload = {
            "operations": [
                {"action": "shell", "args": {"command": "echo 'shell command'"}},
                {"action": "files", "args": {"action": "write", "path": test_file, "content": "file content"}},
                {"action": "files", "args": {"action": "read", "path": test_file}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3
        # Check shell command
        assert data["results"][0]["action"] == "shell"
        assert "shell command" in data["results"][0]["stdout"]
        # Check file write
        assert data["results"][1]["action"] == "files"
        # Check file read
        assert data["results"][2]["action"] == "files"
        assert data["results"][2]["result"]["content"] == "file content"

    def test_batch_dry_run(self, client, auth_headers, temp_dir):
        """Test batch dry run."""
        test_file = os.path.join(temp_dir, "dry_run_test.txt")

        payload = {
            "operations": [
                {"action": "shell", "args": {"command": "echo 'dry run test'"}},
                {"action": "files", "args": {"action": "write", "path": test_file, "content": "should not exist"}}
            ],
            "dry_run": True
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["dry_run"] is True
        assert data["results"][1]["dry_run"] is True
        # Verify file was NOT created
        assert not os.path.exists(test_file)

    def test_batch_empty_operations(self, client, auth_headers):
        """Test batch with empty operations."""
        payload = {
            "operations": []
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 0

    def test_batch_missing_operations(self, client, auth_headers):
        """Test batch with missing operations."""
        payload = {}
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_batch"

    def test_batch_invalid_operation_format(self, client, auth_headers):
        """Test batch with invalid operation format."""
        payload = {
            "operations": [
                "invalid_operation_string",
                {"action": "shell", "args": {"command": "echo test"}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        # First operation should fail
        assert "error" in data["results"][0]
        assert data["results"][0]["error"]["code"] == "invalid_operation"
        # Second operation should succeed
        assert data["results"][1]["action"] == "shell"

    def test_batch_missing_action(self, client, auth_headers):
        """Test batch operation missing action."""
        payload = {
            "operations": [
                {"args": {"command": "echo test"}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert "error" in data["results"][0]
        assert data["results"][0]["error"]["code"] == "missing_action"

    def test_batch_shell_missing_command(self, client, auth_headers):
        """Test batch shell operation missing command."""
        payload = {
            "operations": [
                {"action": "shell", "args": {}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert "error" in data["results"][0]
        assert data["results"][0]["error"]["code"] == "missing_command"

    def test_batch_unsupported_action(self, client, auth_headers):
        """Test batch with unsupported action."""
        payload = {
            "operations": [
                {"action": "unsupported_action", "args": {}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert "error" in data["results"][0]
        assert data["results"][0]["error"]["code"] == "unsupported_action"

    def test_batch_error_handling(self, client, auth_headers, temp_dir):
        """Test batch error handling and continuation."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")

        payload = {
            "operations": [
                {"action": "shell", "args": {"command": "echo 'success'"}},
                {"action": "files", "args": {"action": "read", "path": nonexistent_file}},
                {"action": "shell", "args": {"command": "echo 'after error'"}}
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3
        # First operation should succeed
        assert data["results"][0]["status"] == 200
        assert "success" in data["results"][0]["stdout"]
        # Second operation should fail
        assert "error" in data["results"][1]["result"]
        assert data["results"][1]["result"]["error"]["code"] == "not_found"
        # Third operation should still succeed
        assert data["results"][2]["status"] == 200
        assert "after error" in data["results"][2]["stdout"]

    def test_batch_large_number_operations(self, client, auth_headers):
        """Test batch with many operations."""
        operations = []
        for i in range(10):
            operations.append({
                "action": "shell",
                "args": {"command": f"echo 'operation {i}'"}
            })

        payload = {
            "operations": operations
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 10
        for i, result in enumerate(data["results"]):
            assert result["status"] == 200
            assert f"operation {i}" in result["stdout"]

    def test_batch_nested_operations(self, client, auth_headers, temp_dir):
        """Test batch with nested/complex operations."""
        test_file = os.path.join(temp_dir, "nested_test.txt")

        payload = {
            "operations": [
                {
                    "action": "files",
                    "args": {
                        "action": "write",
                        "path": test_file,
                        "content": "initial content"
                    }
                },
                {
                    "action": "shell",
                    "args": {
                        "command": f"cat {test_file}"
                    }
                },
                {
                    "action": "files",
                    "args": {
                        "action": "write",
                        "path": test_file,
                        "content": "modified content"
                    }
                },
                {
                    "action": "shell",
                    "args": {
                        "command": f"cat {test_file}"
                    }
                }
            ]
        }
        response = client.post("/batch", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 4
        # Check that operations executed in sequence
        assert "initial content" in data["results"][1]["stdout"]
        assert "modified content" in data["results"][3]["stdout"]

    def test_batch_alternate_endpoint(self, client, auth_headers):
        """Test batch endpoint with alternate URL."""
        payload = {
            "operations": [
                {"action": "shell", "args": {"command": "echo 'alternate endpoint'"}}
            ]
        }
        # Test both /batch and /batch/ endpoints
        response1 = client.post("/batch", headers=auth_headers, json=payload)
        response2 = client.post("/batch/", headers=auth_headers, json=payload)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert "results" in data1
        assert "results" in data2
        assert len(data1["results"]) == 1
        assert len(data2["results"]) == 1