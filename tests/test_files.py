import pytest
import os
import json

class TestFilesEndpoints:
    """Test suite for /files endpoint operations."""

    def test_write_file(self, client, auth_headers, temp_dir):
        """Test writing a file."""
        test_file = os.path.join(temp_dir, "test_write.txt")
        payload = {
            "action": "write",
            "path": test_file,
            "content": "Hello, World!"
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "status" in data["result"]
        assert data["result"]["status"] == 200
        # Verify file was created
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "Hello, World!"

    def test_read_file(self, client, auth_headers, temp_file):
        """Test reading a file."""
        payload = {
            "action": "read",
            "path": temp_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "content" in data["result"]
        assert data["result"]["content"] == "test content\n"
        assert data["result"]["status"] == 200

    def test_read_nonexistent_file(self, client, auth_headers, temp_dir):
        """Test reading a nonexistent file."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        payload = {
            "action": "read",
            "path": nonexistent_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "not_found"
        assert data["result"]["status"] == 404

    def test_delete_file(self, client, auth_headers, temp_file):
        """Test deleting a file."""
        payload = {
            "action": "delete",
            "path": temp_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == 200
        # Verify file was deleted
        assert not os.path.exists(temp_file)

    def test_delete_nonexistent_file(self, client, auth_headers, temp_dir):
        """Test deleting a nonexistent file."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        payload = {
            "action": "delete",
            "path": nonexistent_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "not_found"
        assert data["result"]["status"] == 404

    def test_stat_file(self, client, auth_headers, temp_file):
        """Test getting file stats."""
        payload = {
            "action": "stat",
            "path": temp_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "size" in data["result"]
        assert "mtime" in data["result"]
        assert "ctime" in data["result"]
        assert data["result"]["status"] == 200
        assert data["result"]["size"] == 13  # "test content" + newline is 13 characters

    def test_exists_file(self, client, auth_headers, temp_file, temp_dir):
        """Test checking if file exists."""
        # Test existing file
        payload = {
            "action": "exists",
            "path": temp_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["exists"] is True
        assert data["result"]["status"] == 200

        # Test nonexistent file
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        payload = {
            "action": "exists",
            "path": nonexistent_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["exists"] is False
        assert data["result"]["status"] == 200

    def test_list_directory(self, client, auth_headers, temp_dir, temp_file):
        """Test listing directory contents."""
        payload = {
            "action": "list",
            "path": temp_dir
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "items" in data["result"]
        assert data["result"]["status"] == 200
        assert "test_file.txt" in data["result"]["items"]

    def test_list_nonexistent_directory(self, client, auth_headers, temp_dir):
        """Test listing a nonexistent directory."""
        nonexistent_dir = os.path.join(temp_dir, "nonexistent_dir")
        payload = {
            "action": "list",
            "path": nonexistent_dir
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "not_a_directory"
        assert data["result"]["status"] == 400

    def test_copy_file(self, client, auth_headers, temp_file, temp_dir):
        """Test copying a file."""
        dest_file = os.path.join(temp_dir, "copied_file.txt")
        payload = {
            "action": "copy",
            "path": temp_file,
            "target_path": dest_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == 200
        # Verify copy was created
        assert os.path.exists(dest_file)
        with open(dest_file, "r") as f:
            assert f.read() == "test content\n"

    def test_copy_nonexistent_file(self, client, auth_headers, temp_dir):
        """Test copying a nonexistent file."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        dest_file = os.path.join(temp_dir, "dest.txt")
        payload = {
            "action": "copy",
            "path": nonexistent_file,
            "target_path": dest_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "not_found"
        assert data["result"]["status"] == 404

    def test_move_file(self, client, auth_headers, temp_file, temp_dir):
        """Test moving a file."""
        dest_file = os.path.join(temp_dir, "moved_file.txt")
        payload = {
            "action": "move",
            "path": temp_file,
            "target_path": dest_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == 200
        # Verify file was moved
        assert not os.path.exists(temp_file)
        assert os.path.exists(dest_file)
        with open(dest_file, "r") as f:
            assert f.read() == "test content\n"

    def test_batch_operations(self, client, auth_headers, temp_dir):
        """Test batch file operations."""
        file1 = os.path.join(temp_dir, "batch1.txt")
        file2 = os.path.join(temp_dir, "batch2.txt")
        payload = {
            "operations": [
                {
                    "action": "write",
                    "path": file1,
                    "content": "content1"
                },
                {
                    "action": "write",
                    "path": file2,
                    "content": "content2"
                },
                {
                    "action": "read",
                    "path": file1
                }
            ]
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3
        # Check first operation (write)
        assert data["results"][0]["status"] == 200
        # Check second operation (write)
        assert data["results"][1]["status"] == 200
        # Check third operation (read)
        assert data["results"][2]["content"] == "content1"
        assert data["results"][2]["status"] == 200
        # Verify files were created
        assert os.path.exists(file1)
        assert os.path.exists(file2)

    def test_fault_injection_permission(self, client, auth_headers, temp_file):
        """Test permission fault injection."""
        payload = {
            "action": "read",
            "path": temp_file,
            "fault": "permission"
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "permission_denied"
        assert data["result"]["status"] == 403

    def test_fault_injection_io(self, client, auth_headers, temp_file):
        """Test IO fault injection."""
        payload = {
            "action": "read",
            "path": temp_file,
            "fault": "io"
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "io_error"
        assert data["result"]["status"] == 500

    def test_invalid_action(self, client, auth_headers, temp_file):
        """Test invalid action."""
        payload = {
            "action": "invalid_action",
            "path": temp_file
        }
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "unsupported_action"
        assert data["result"]["status"] == 400

    def test_missing_required_fields(self, client, auth_headers):
        """Test missing required fields."""
        # Missing action
        payload = {"path": "/some/path"}
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "missing_field"

        # Missing path
        payload = {"action": "read"}
        response = client.post("/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "missing_field"