import pytest
import os

class TestRefactorEndpoints:
    """Test suite for /refactor endpoint operations."""

    def test_refactor_single_file(self, client, auth_headers, temp_file):
        """Test refactoring a single file."""
        payload = {
            "search": "test content",
            "replace": "modified content",
            "files": [temp_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 1
        assert data["result"][0]["file"] == temp_file
        assert data["result"][0]["changed"] is True
        # Verify file was actually modified
        with open(temp_file, "r") as f:
            assert f.read() == "modified content\n"

    def test_refactor_multiple_files(self, client, auth_headers, temp_dir):
        """Test refactoring multiple files."""
        file1 = os.path.join(temp_dir, "file1.txt")
        file2 = os.path.join(temp_dir, "file2.txt")
        with open(file1, "w") as f:
            f.write("old text in file1")
        with open(file2, "w") as f:
            f.write("old text in file2")

        payload = {
            "search": "old text",
            "replace": "new text",
            "files": [file1, file2]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 2
        for result in data["result"]:
            assert result["changed"] is True
        # Verify files were modified
        with open(file1, "r") as f:
            assert f.read() == "new text in file1"
        with open(file2, "r") as f:
            assert f.read() == "new text in file2"

    def test_refactor_dry_run(self, client, auth_headers, temp_file):
        """Test refactor dry run."""
        original_content = "original content"
        with open(temp_file, "w") as f:
            f.write(original_content)

        payload = {
            "search": "original",
            "replace": "modified",
            "files": [temp_file],
            "dry_run": True
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "No matches found" not in data["result"]  # Should find matches
        # Verify file was NOT modified
        with open(temp_file, "r") as f:
            assert f.read() == original_content

    def test_refactor_no_matches(self, client, auth_headers, temp_file):
        """Test refactor with no matches."""
        payload = {
            "search": "nonexistent",
            "replace": "replacement",
            "files": [temp_file],
            "dry_run": True
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"] == "No matches found."

    def test_refactor_nonexistent_file(self, client, auth_headers, temp_dir):
        """Test refactoring nonexistent file."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        payload = {
            "search": "test",
            "replace": "modified",
            "files": [nonexistent_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 0  # Nonexistent files are skipped

    def test_refactor_mixed_files(self, client, auth_headers, temp_dir, temp_file):
        """Test refactoring mix of existing and nonexistent files."""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.txt")
        payload = {
            "search": "test content",
            "replace": "modified content",
            "files": [temp_file, nonexistent_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 1
        assert data["result"][0]["file"] == temp_file
        assert data["result"][0]["changed"] is True

    def test_refactor_multiple_replacements(self, client, auth_headers, temp_dir):
        """Test multiple replacements in one file."""
        test_file = os.path.join(temp_dir, "multi_replace.txt")
        with open(test_file, "w") as f:
            f.write("hello world hello universe")

        payload = {
            "search": "hello",
            "replace": "hi",
            "files": [test_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 1
        assert data["result"][0]["changed"] is True
        # Verify multiple replacements
        with open(test_file, "r") as f:
            content = f.read()
            assert content == "hi world hi universe"
            assert content.count("hi") == 2

    def test_refactor_regex_patterns(self, client, auth_headers, temp_dir):
        """Test refactoring with regex-like patterns."""
        test_file = os.path.join(temp_dir, "regex_test.txt")
        with open(test_file, "w") as f:
            f.write("var1 = 1\nvar2 = 2\nvar3 = 3")

        payload = {
            "search": "var",
            "replace": "variable",
            "files": [test_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 1
        assert data["result"][0]["changed"] is True
        # Verify replacements
        with open(test_file, "r") as f:
            content = f.read()
            assert "variable1 = 1" in content
            assert "variable2 = 2" in content
            assert "variable3 = 3" in content

    def test_refactor_empty_search(self, client, auth_headers, temp_file):
        """Test refactor with empty search string."""
        payload = {
            "search": "",
            "replace": "prefix",
            "files": [temp_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Empty search should replace at beginning
        with open(temp_file, "r") as f:
            content = f.read()
            assert content.startswith("prefix")

    def test_refactor_empty_replace(self, client, auth_headers, temp_dir):
        """Test refactor with empty replace string."""
        test_file = os.path.join(temp_dir, "empty_replace.txt")
        with open(test_file, "w") as f:
            f.write("remove this text")

        payload = {
            "search": "remove this ",
            "replace": "",
            "files": [test_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"][0]["changed"] is True
        # Verify text was removed
        with open(test_file, "r") as f:
            assert f.read() == "text"

    def test_refactor_case_sensitive(self, client, auth_headers, temp_dir):
        """Test case-sensitive refactoring."""
        test_file = os.path.join(temp_dir, "case_test.txt")
        with open(test_file, "w") as f:
            f.write("Hello hello HELLO")

        payload = {
            "search": "Hello",
            "replace": "Hi",
            "files": [test_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"][0]["changed"] is True
        # Verify only first occurrence was replaced
        with open(test_file, "r") as f:
            content = f.read()
            assert content == "Hi hello HELLO"

    def test_refactor_newlines(self, client, auth_headers, temp_dir):
        """Test refactoring with newlines."""
        test_file = os.path.join(temp_dir, "newline_test.txt")
        with open(test_file, "w") as f:
            f.write("line1\nline2\nline3")

        payload = {
            "search": "\n",
            "replace": " | ",
            "files": [test_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"][0]["changed"] is True
        # Verify newlines were replaced
        with open(test_file, "r") as f:
            content = f.read()
            assert content == "line1 | line2 | line3"

    def test_refactor_fault_injection_io(self, client, auth_headers, temp_file):
        """Test IO fault injection."""
        payload = {
            "search": "test",
            "replace": "modified",
            "files": [temp_file],
            "fault": "io"
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "io_error"
        assert data["status"] == 500

    def test_refactor_missing_search(self, client, auth_headers, temp_file):
        """Test missing search parameter."""
        payload = {
            "replace": "replacement",
            "files": [temp_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "internal_error"

    def test_refactor_missing_replace(self, client, auth_headers, temp_file):
        """Test missing replace parameter."""
        payload = {
            "search": "search",
            "files": [temp_file]
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Should work with empty replace string

    def test_refactor_missing_files(self, client, auth_headers):
        """Test missing files parameter."""
        payload = {
            "search": "search",
            "replace": "replace"
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "internal_error"

    def test_refactor_empty_files_list(self, client, auth_headers):
        """Test empty files list."""
        payload = {
            "search": "search",
            "replace": "replace",
            "files": []
        }
        response = client.post("/refactor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 0